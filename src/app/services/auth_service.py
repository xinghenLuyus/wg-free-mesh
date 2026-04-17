from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_token_secret,
    hash_password,
    is_password_hash,
    verify_password,
)
from app.repositories.sqlite import store

ADMIN_USERNAME = "admin"
ADMIN_DISPLAY_NAME = "管理员"
SESSION_TOKEN_KIND = "session"
DOWNLOAD_TOKEN_KIND = "download"
GLOBAL_PERMISSION = "*"
DOWNLOAD_PERMISSION = "config.node.download"


@dataclass(frozen=True, kw_only=True)
class TokenGrant:
    token_kind: str
    permissions: frozenset[str]
    expires_at: datetime | None = None

    def allows(self, permission: str) -> bool:
        return GLOBAL_PERMISSION in self.permissions or permission in self.permissions


@dataclass(frozen=True, kw_only=True)
class CurrentUser(TokenGrant):
    username: str
    display_name: str


@dataclass(frozen=True, kw_only=True)
class DownloadGrant(TokenGrant):
    username: str
    config_id: str
    node_id: str


class AuthService:
    password_key = "auth_admin_password_hash"
    legacy_password_key = "auth_password_hash"
    token_secret_key = "auth_token_secret"
    password_updated_key = "auth_password_updated_at"

    def setup_required(self) -> bool:
        return not is_password_hash(self._read_password_hash())

    def auth_state(self, token: str | None = None) -> dict[str, object]:
        if self.setup_required():
            return self._state_payload(setup_required=True, user=None)
        user = self.optional_user(token)
        return self._state_payload(setup_required=False, user=user)

    def setup(self, password: str) -> dict[str, object]:
        if not self.setup_required():
            raise AppError("AUTH_ALREADY_INITIALIZED", "管理员密码已初始化", 409)
        self._write_password_hash(hash_password(password))
        self._write_token_secret(generate_token_secret())
        return self._token_session()

    def login(self, username: str, password: str) -> dict[str, object]:
        if self.setup_required():
            raise AppError("AUTH_SETUP_REQUIRED", "需要先设置初始管理员密码", 428)
        if username.strip() != ADMIN_USERNAME or not verify_password(password, self._read_password_hash()):
            raise AppError("AUTH_FAILED", "用户名或密码错误", 401)
        return self._token_session()

    def change_password(self, current_password: str, new_password: str) -> None:
        if self.setup_required():
            raise AppError("AUTH_SETUP_REQUIRED", "需要先设置初始管理员密码", 428)
        if not verify_password(current_password, self._read_password_hash()):
            raise AppError("AUTH_FAILED", "当前密码不正确", 401)
        self._write_password_hash(hash_password(new_password))
        self._write_token_secret(generate_token_secret())

    def require_user(self, token: str | None) -> CurrentUser:
        if self.setup_required():
            raise AppError("AUTH_SETUP_REQUIRED", "需要先设置初始管理员密码", 428)
        if not token:
            raise AppError("AUTH_REQUIRED", "请先登录", 401)
        return self._user_from_token(token)

    def optional_user(self, token: str | None) -> CurrentUser | None:
        if not token or self.setup_required():
            return None
        try:
            return self._user_from_token(token)
        except AppError:
            return None

    def create_download_token(self, *, config_id: str, node_id: str, user: CurrentUser) -> dict[str, object]:
        token, expires_at = create_access_token(
            subject=user.username,
            secret=self._read_token_secret(),
            expires_delta=timedelta(minutes=settings.auth_download_token_expire_minutes),
            claims={
                "kind": DOWNLOAD_TOKEN_KIND,
                "permissions": [DOWNLOAD_PERMISSION],
                "resource": {"config_id": config_id, "node_id": node_id},
            },
        )
        return {
            "access_token": token,
            "token_type": "download",
            "expires_at": expires_at.isoformat(),
        }

    def require_download_grant(self, token: str | None, *, config_id: str, node_id: str) -> DownloadGrant:
        if not token:
            raise AppError("DOWNLOAD_TOKEN_REQUIRED", "请先生成下载地址", 401)
        payload = decode_access_token(token, self._read_token_secret())
        if payload.get("kind") != DOWNLOAD_TOKEN_KIND:
            raise AppError("INVALID_DOWNLOAD_TOKEN", "下载凭证无效", 401)
        permissions = self._permissions_from_payload(payload)
        if DOWNLOAD_PERMISSION not in permissions:
            raise AppError("INVALID_DOWNLOAD_TOKEN", "下载凭证无效", 401)
        resource = payload.get("resource")
        if not isinstance(resource, dict):
            raise AppError("INVALID_DOWNLOAD_TOKEN", "下载凭证无效", 401)
        grant_config_id = str(resource.get("config_id") or "")
        grant_node_id = str(resource.get("node_id") or "")
        if grant_config_id != config_id or grant_node_id != node_id:
            raise AppError("DOWNLOAD_TOKEN_SCOPE_MISMATCH", "下载凭证与当前节点不匹配", 403)
        return DownloadGrant(
            token_kind=DOWNLOAD_TOKEN_KIND,
            permissions=frozenset(permissions),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), UTC),
            username=str(payload.get("sub") or ADMIN_USERNAME),
            config_id=grant_config_id,
            node_id=grant_node_id,
        )

    def _read_password_hash(self) -> str | None:
        current = store.read_setting(self.password_key)
        if current:
            return current
        return store.read_setting(self.legacy_password_key)

    def _write_password_hash(self, value: str) -> None:
        store.write_setting(self.password_key, value)
        store.write_setting(self.password_updated_key, datetime.now(UTC).isoformat())

    def _read_token_secret(self) -> str:
        secret = store.read_setting(self.token_secret_key)
        if secret:
            return secret
        secret = generate_token_secret()
        self._write_token_secret(secret)
        return secret

    def _write_token_secret(self, value: str) -> None:
        store.write_setting(self.token_secret_key, value)

    def _user_from_token(self, token: str) -> CurrentUser:
        payload = decode_access_token(token, self._read_token_secret())
        if payload.get("kind") != SESSION_TOKEN_KIND:
            raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
        if payload.get("sub") != ADMIN_USERNAME:
            raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
        permissions = self._permissions_from_payload(payload)
        if GLOBAL_PERMISSION not in permissions:
            raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
        expires_at = datetime.fromtimestamp(int(payload["exp"]), UTC)
        return CurrentUser(
            token_kind=SESSION_TOKEN_KIND,
            permissions=frozenset(permissions),
            expires_at=expires_at,
            username=ADMIN_USERNAME,
            display_name=ADMIN_DISPLAY_NAME,
        )

    def _token_session(self) -> dict[str, object]:
        token, expires_at = create_access_token(
            subject=ADMIN_USERNAME,
            secret=self._read_token_secret(),
            expires_delta=timedelta(minutes=settings.auth_token_expire_minutes),
            claims={"kind": SESSION_TOKEN_KIND, "permissions": [GLOBAL_PERMISSION]},
        )
        return {
            **self._state_payload(
                False,
                CurrentUser(
                    token_kind=SESSION_TOKEN_KIND,
                    permissions=frozenset({GLOBAL_PERMISSION}),
                    expires_at=expires_at,
                    username=ADMIN_USERNAME,
                    display_name=ADMIN_DISPLAY_NAME,
                ),
            ),
            "access_token": token,
            "token_type": "bearer",
        }

    @staticmethod
    def _permissions_from_payload(payload: dict[str, object]) -> list[str]:
        raw = payload.get("permissions")
        if not isinstance(raw, list):
            raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
        permissions = [str(item).strip() for item in raw if str(item).strip()]
        if not permissions:
            raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
        return permissions

    @staticmethod
    def _state_payload(setup_required: bool, user: CurrentUser | None) -> dict[str, object]:
        return {
            "setup_required": setup_required,
            "authenticated": user is not None,
            "username": user.username if user else "",
            "display_name": user.display_name if user else "",
            "expires_at": user.expires_at.isoformat() if user and user.expires_at else None,
        }


auth_service = AuthService()
