# mypy: disable-error-code=attr-defined
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from app.core.errors import AppError
from app.data.connection import connect
from app.domain.models import new_id, now_utc


class McpAccessRepositoryMixin:
    def list_mcp_tokens(self) -> list[dict[str, object]]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM mcp_tokens ORDER BY created_at DESC").fetchall()
        return [self._mcp_token_payload(row) for row in rows]

    def create_mcp_token(self, payload: dict[str, object]) -> dict[str, object]:
        name = str(payload.get("name") or "").strip()
        permission = str(payload.get("permission") or "").strip()
        expires_at = str(payload.get("expires_at") or "").strip()
        if not name:
            raise AppError("MCP_TOKEN_NAME_REQUIRED", "MCP token name is required", 400)
        if permission not in {"read", "write"}:
            raise AppError("MCP_TOKEN_PERMISSION_INVALID", "MCP token permission must be read or write", 400)
        try:
            expires = datetime.fromisoformat(expires_at)
        except ValueError as exc:
            raise AppError("MCP_TOKEN_EXPIRY_INVALID", "MCP token expiry is invalid", 400) from exc
        if expires.tzinfo is None:
            raise AppError("MCP_TOKEN_EXPIRY_INVALID", "MCP token expiry must include timezone", 400)
        if expires.astimezone(UTC) <= datetime.now(UTC):
            raise AppError("MCP_TOKEN_EXPIRY_INVALID", "MCP token expiry must be in the future", 400)

        now = now_utc().isoformat()
        token_id = new_id("mcp")
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO mcp_tokens (id, name, token, permission, expires_at, revoked_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (token_id, name, f"wfm_mcp_{secrets.token_urlsafe(36)}", permission, expires.isoformat(), now, now),
            )
            row = connection.execute("SELECT * FROM mcp_tokens WHERE id = ?", (token_id,)).fetchone()
        assert row is not None
        return self._mcp_token_payload(row)

    def revoke_mcp_token(self, token_id: str) -> dict[str, object]:
        now = now_utc().isoformat()
        with connect() as connection:
            row = connection.execute("SELECT * FROM mcp_tokens WHERE id = ?", (token_id,)).fetchone()
            if row is None:
                raise AppError("MCP_TOKEN_NOT_FOUND", "MCP token not found", 404)
            if not row["revoked_at"]:
                connection.execute("UPDATE mcp_tokens SET revoked_at = ?, updated_at = ? WHERE id = ?", (now, now, token_id))
            updated = connection.execute("SELECT * FROM mcp_tokens WHERE id = ?", (token_id,)).fetchone()
        assert updated is not None
        return self._mcp_token_payload(updated)

    def find_active_mcp_token(self, token: str) -> dict[str, object] | None:
        raw_token = token.strip()
        if not raw_token:
            return None
        with connect() as connection:
            row = connection.execute("SELECT * FROM mcp_tokens WHERE token = ?", (raw_token,)).fetchone()
        if row is None or row["revoked_at"]:
            return None
        try:
            expires = datetime.fromisoformat(str(row["expires_at"]))
        except ValueError:
            return None
        if expires.tzinfo is None or expires.astimezone(UTC) <= datetime.now(UTC):
            return None
        return self._mcp_token_payload(row)

    def list_mcp_audit_logs(
        self,
        limit: int = 100,
        *,
        created_from: str | None = None,
        created_to: str | None = None,
        token_name: str = "",
        target_name: str = "",
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 500))
        clauses: list[str] = []
        params: list[object] = []
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)
        token_filter = token_name.strip().lower()
        if token_filter:
            clauses.append("LOWER(token_name) LIKE ?")
            params.append(f"%{token_filter}%")
        target_filter = target_name.strip().lower()
        if target_filter:
            clauses.append("LOWER(target_name) LIKE ?")
            params.append(f"%{target_filter}%")
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(bounded_limit)
        with connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM mcp_audit_logs {where_sql} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._mcp_audit_payload(row) for row in rows]

    def delete_mcp_audit_logs(self, *, created_from: str, created_to: str) -> dict[str, object]:
        with connect() as connection:
            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM mcp_audit_logs WHERE created_at >= ? AND created_at <= ?",
                (created_from, created_to),
            ).fetchone()
            deleted_count = int(count_row["count"]) if count_row else 0
            connection.execute(
                "DELETE FROM mcp_audit_logs WHERE created_at >= ? AND created_at <= ?",
                (created_from, created_to),
            )
        return {"deleted_count": deleted_count}

    def create_mcp_audit_log(self, payload: dict[str, object]) -> dict[str, object]:
        audit_id = new_id("mcpaudit")
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO mcp_audit_logs (
                    id, token_id, token_name, permission, target_kind, target_name, summary, impact,
                    confirmation_required, confirmation_result, result, error_code, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    payload.get("token_id"),
                    str(payload.get("token_name") or ""),
                    str(payload.get("permission") or ""),
                    str(payload.get("target_kind") or ""),
                    str(payload.get("target_name") or ""),
                    str(payload.get("summary") or ""),
                    str(payload.get("impact") or ""),
                    bool(payload.get("confirmation_required")),
                    str(payload.get("confirmation_result") or ""),
                    str(payload.get("result") or ""),
                    str(payload.get("error_code") or ""),
                    now_utc().isoformat(),
                ),
            )
            row = connection.execute("SELECT * FROM mcp_audit_logs WHERE id = ?", (audit_id,)).fetchone()
        assert row is not None
        return self._mcp_audit_payload(row)

    @staticmethod
    def _mcp_token_payload(row) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "token": str(row["token"]),
            "permission": str(row["permission"]),
            "expires_at": str(row["expires_at"]),
            "revoked_at": str(row["revoked_at"]) if row["revoked_at"] else None,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _mcp_audit_payload(row) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "token_id": str(row["token_id"]) if row["token_id"] else None,
            "token_name": str(row["token_name"]),
            "permission": str(row["permission"]),
            "target_kind": str(row["target_kind"]),
            "target_name": str(row["target_name"]),
            "summary": str(row["summary"]),
            "impact": str(row["impact"]),
            "confirmation_required": bool(row["confirmation_required"]),
            "confirmation_result": str(row["confirmation_result"]),
            "result": str(row["result"]),
            "error_code": str(row["error_code"]),
            "created_at": str(row["created_at"]),
        }
