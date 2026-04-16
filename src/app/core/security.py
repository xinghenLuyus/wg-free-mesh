from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.errors import AppError

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000
TOKEN_ALGORITHM = "HS256"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def generate_token_secret() -> str:
    return secrets.token_urlsafe(48)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest}"


def is_password_hash(value: str | None) -> bool:
    if not value:
        return False
    parts = value.split("$")
    return len(parts) == 4 and parts[0] == PASSWORD_ALGORITHM


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not is_password_hash(stored_hash):
        return False
    assert stored_hash is not None
    _, iterations_text, salt, expected = stored_hash.split("$", 3)
    try:
        iterations = int(iterations_text)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    ).hex()
    return secrets.compare_digest(digest, expected)


def create_access_token(
    *,
    subject: str,
    secret: str,
    expires_delta: timedelta,
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    header = {"alg": TOKEN_ALGORITHM, "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    signing_input = ".".join(
        [
            _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256)
    return f"{signing_input}.{_b64encode(signature.digest())}", expires_at


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise AppError("INVALID_TOKEN", "登录凭证无效", 401) from exc

    signing_input = f"{header_part}.{payload_part}"
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256)
    if not secrets.compare_digest(_b64encode(expected.digest()), signature_part):
        raise AppError("INVALID_TOKEN", "登录凭证无效", 401)

    try:
        header = json.loads(_b64decode(header_part))
        payload = json.loads(_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AppError("INVALID_TOKEN", "登录凭证无效", 401) from exc

    if header.get("alg") != TOKEN_ALGORITHM:
        raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise AppError("INVALID_TOKEN", "登录凭证无效", 401)
    if datetime.now(UTC).timestamp() >= exp:
        raise AppError("TOKEN_EXPIRED", "登录凭证已过期", 401)
    return payload
