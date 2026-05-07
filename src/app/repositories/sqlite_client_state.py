# mypy: disable-error-code=attr-defined
from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, cast

from app.core.errors import AppError
from app.domain.models import ConnectivityState, NodeType, WgRuntimeState, now_utc, sha256_text
from app.infrastructure.database import connect
from app.repositories.row_mappers import bool_value as _bool_value, parse_datetime as _parse_datetime


class SQLiteClientStateMixin:
    HEARTBEAT_TIMEOUT = timedelta(minutes=45)

    @staticmethod
    def _normalize_client_text(value: str, limit: int = 64) -> str:
        return value.strip()[:limit]

    @staticmethod
    def _client_platform_label(platform: str) -> str:
        normalized = platform.strip().lower()
        labels = {
            "windows": "Windows",
            "win32": "Windows",
            "linux": "Linux",
            "darwin": "macOS",
            "macos": "macOS",
        }
        return labels.get(normalized, platform.strip())

    def _client_version_label(self, platform: object, version: object) -> str:
        platform_label = self._client_platform_label(str(platform or ""))
        version_text = str(version or "").strip()
        if platform_label and version_text:
            return f"{platform_label} {version_text}"
        return platform_label or version_text

    def _ensure_client_state(self, config_id: str, node_id: str) -> None:
        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO node_client_state
                  (node_id, config_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (node_id, config_id, now, now),
            )

    def get_client_state(self, config_id: str, node_id: str) -> dict[str, object]:
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM node_client_state WHERE config_id = ? AND node_id = ?",
                (config_id, node_id),
            ).fetchone()
        if row is None:
            return {
                "client_initialized": False,
                "client_presence_state": "offline",
            }
        return {
            "client_initialized": _bool_value(row["client_initialized"]),
            "client_platform": row["client_platform"],
            "client_version": row["client_version"],
            "client_hostname": row["client_hostname"],
            "client_version_label": self._client_version_label(row["client_platform"], row["client_version"]),
            "mqtt_username": row["mqtt_username"],
            "mqtt_client_id": row["mqtt_client_id"],
            "client_presence_state": row["client_presence_state"],
            "boot_id": row["boot_id"],
            "session_id": row["session_id"],
            "last_heartbeat_at": row["last_heartbeat_at"],
            "last_detect_ack_at": row["last_detect_ack_at"],
            "last_will_at": row["last_will_at"],
            "last_event": row["last_event"],
            "last_event_at": row["last_event_at"],
        }

    def list_client_states(self, config_id: str) -> dict[str, dict[str, object]]:
        self.get_config(config_id)
        with connect() as connection:
            now = now_utc().isoformat()
            connection.execute(
                """
                INSERT OR IGNORE INTO node_client_state
                  (node_id, config_id, created_at, updated_at)
                SELECT id, config_id, ?, ?
                FROM nodes
                WHERE config_id = ?
                """,
                (now, now, config_id),
            )
            rows = connection.execute(
                "SELECT * FROM node_client_state WHERE config_id = ?",
                (config_id,),
            ).fetchall()
        states: dict[str, dict[str, object]] = {}
        for row in rows:
            node_id = str(row["node_id"])
            states[node_id] = {
                "client_initialized": _bool_value(row["client_initialized"]),
                "client_platform": row["client_platform"],
                "client_version": row["client_version"],
                "client_hostname": row["client_hostname"],
                "client_version_label": self._client_version_label(row["client_platform"], row["client_version"]),
                "mqtt_username": row["mqtt_username"],
                "mqtt_client_id": row["mqtt_client_id"],
                "client_presence_state": row["client_presence_state"],
                "boot_id": row["boot_id"],
                "session_id": row["session_id"],
                "last_heartbeat_at": row["last_heartbeat_at"],
                "last_detect_ack_at": row["last_detect_ack_at"],
                "last_will_at": row["last_will_at"],
                "last_event": row["last_event"],
                "last_event_at": row["last_event_at"],
            }
        return states

    def _reset_runtime_row(
        self,
        connection: object,
        config_id: str,
        node_id: str,
        *,
        reason: str,
        clear_downloaded: bool = False,
    ) -> None:
        now = now_utc().isoformat()
        downloaded_sql = ", client_downloaded = 0, client_downloaded_at = NULL" if clear_downloaded else ""
        cast(Any, connection).execute(
            f"""
            UPDATE endpoint_runtime_status
            SET online = 0,
                connectivity_state = ?,
                wg_running = 0,
                wg_runtime_state = ?,
                heartbeat_client_online = 0,
                heartbeat_wg_online = 0,
                detect_client_online = 0,
                detect_wg_online = 0,
                last_seen = NULL,
                last_probe_sent_at = NULL,
                last_probe_ack_at = NULL,
                last_control_channel_seen_at = NULL,
                last_connectivity_reason = ?,
                updated_at = ?
                {downloaded_sql}
            WHERE config_id = ? AND node_id = ?
            """,
            (ConnectivityState.offline.value, WgRuntimeState.stopped.value, reason, now, config_id, node_id),
        )

    def _reset_client_state_row(self, connection: object, config_id: str, node_id: str) -> None:
        now = now_utc().isoformat()
        cast(Any, connection).execute(
            """
            UPDATE node_client_state
            SET client_initialized = 0,
                client_platform = '',
                client_version = '',
                client_hostname = '',
                mqtt_username = '',
                mqtt_client_id = '',
                bind_token_hash = '',
                bind_token_expires_at = NULL,
                bind_token_used_at = NULL,
                client_presence_state = 'offline',
                boot_id = '',
                session_id = '',
                last_heartbeat_at = NULL,
                last_detect_ack_at = NULL,
                last_will_at = NULL,
                last_event = '',
                last_event_at = NULL,
                updated_at = ?
            WHERE config_id = ? AND node_id = ?
            """,
            (now, config_id, node_id),
        )

    def reconcile_node_operational_state(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            if node.node_type == NodeType.static:
                self._reset_client_state_row(connection, config_id, node_id)
                self._reset_runtime_row(connection, config_id, node_id, reason="static-node", clear_downloaded=True)
            else:
                self._reset_client_state_row(connection, config_id, node_id)
                self._reset_runtime_row(connection, config_id, node_id, reason="dynamic-node-uninitialized", clear_downloaded=True)
        return {
            "runtime": self.get_runtime(config_id, node_id),
            "client_state": self.get_client_state(config_id, node_id),
        }

    def reconcile_runtime_integrity(self) -> None:
        for config in self.list_configs():
            for node in self.list_nodes(config.id):
                if node.node_type == NodeType.static:
                    self.reconcile_node_operational_state(config.id, node.id)

    def create_client_bind_token(self, config_id: str, node_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        node = self.get_node(node_id)
        if node.config_id != config.id:
            raise AppError("NODE_CONFIG_MISMATCH", "Node does not belong to config", 400)
        if node.node_type != NodeType.dynamic:
            raise AppError("CLIENT_BIND_STATIC_NODE", "Static node cannot bind client", 400)
        token = secrets.token_urlsafe(32)
        expires_at = now_utc() + timedelta(minutes=5)
        now = now_utc().isoformat()
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            connection.execute(
                """
                UPDATE node_client_state
                SET bind_token_hash = ?, bind_token_expires_at = ?, bind_token_used_at = NULL, updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (sha256_text(token), expires_at.isoformat(), now, config_id, node_id),
            )
        return {"token": token, "expires_at": expires_at, "config": config, "node": node}

    def validate_client_bind_token(self, token: str) -> dict[str, object]:
        token_hash = sha256_text(token.strip())
        now = now_utc()
        with connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM node_client_state
                WHERE bind_token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            raise AppError("CLIENT_BIND_TOKEN_INVALID", "Client bind token is invalid", 401)
        if row["bind_token_used_at"]:
            raise AppError("CLIENT_BIND_TOKEN_USED", "Client bind token has already been used", 409)
        expires_at = _parse_datetime(row["bind_token_expires_at"])
        if expires_at is None or expires_at <= now:
            raise AppError("CLIENT_BIND_TOKEN_EXPIRED", "Client bind token has expired", 401)
        node = self.get_node(row["node_id"])
        config = self.get_config(row["config_id"])
        if node.node_type != NodeType.dynamic or not config.enabled:
            raise AppError("CLIENT_BIND_NOT_ALLOWED", "Client bind is not allowed for this node", 403)
        return {"config": config, "node": node, "expires_at": expires_at}

    def mark_client_bound(
        self,
        config_id: str,
        node_id: str,
        *,
        username: str,
        client_id: str,
        platform: str = "",
        version: str = "",
        hostname: str = "",
    ) -> dict[str, object]:
        now = now_utc().isoformat()
        self._ensure_client_state(config_id, node_id)
        client_platform = self._normalize_client_text(platform)
        client_version = self._normalize_client_text(version)
        client_hostname = self._normalize_client_text(hostname, limit=128)
        with connect() as connection:
            connection.execute(
                """
                UPDATE node_client_state
                SET client_initialized = 1,
                    client_platform = ?,
                    client_version = ?,
                    client_hostname = ?,
                    mqtt_username = ?,
                    mqtt_client_id = ?,
                    bind_token_used_at = ?,
                    client_presence_state = 'offline',
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (client_platform, client_version, client_hostname, username, client_id, now, now, config_id, node_id),
            )
        return self.get_client_state(config_id, node_id)

    def reset_client_state(self, config_id: str, node_id: str) -> dict[str, object]:
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            self._reset_client_state_row(connection, config_id, node_id)
            self._reset_runtime_row(connection, config_id, node_id, reason="client-reset", clear_downloaded=True)
        return self.get_client_state(config_id, node_id)

    def reconcile_client_timeouts(self, config_id: str | None = None) -> None:
        cutoff = (now_utc() - self.HEARTBEAT_TIMEOUT).isoformat()
        params: tuple[object, ...]
        config_filter = ""
        if config_id:
            config_filter = "AND config_id = ?"
            params = (cutoff, config_id)
        else:
            params = (cutoff,)
        now = now_utc().isoformat()
        with connect() as connection:
            rows = connection.execute(
                f"""
                SELECT config_id, node_id
                FROM node_client_state
                WHERE client_initialized = 1
                  AND last_heartbeat_at IS NOT NULL
                  AND last_heartbeat_at < ?
                  {config_filter}
                """,
                params,
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE node_client_state
                    SET client_presence_state = 'offline', updated_at = ?
                    WHERE config_id = ? AND node_id = ?
                    """,
                    (now, row["config_id"], row["node_id"]),
                )
                connection.execute(
                    """
                    UPDATE endpoint_runtime_status
                    SET online = 0,
                        connectivity_state = ?,
                        wg_running = 0,
                        wg_runtime_state = ?,
                        heartbeat_client_online = 0,
                        heartbeat_wg_online = 0,
                        last_connectivity_reason = ?,
                        updated_at = ?
                    WHERE config_id = ? AND node_id = ?
                    """,
                    (
                        ConnectivityState.offline.value,
                        WgRuntimeState.stopped.value,
                        "heartbeat-timeout",
                        now,
                        row["config_id"],
                        row["node_id"],
                    ),
                )

    def list_detect_targets(self) -> list[dict[str, str]]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT n.config_id, n.id AS node_id
                FROM nodes n
                JOIN configs c ON c.id = n.config_id
                JOIN node_client_state s ON s.config_id = n.config_id AND s.node_id = n.id
                WHERE c.enabled = 1
                  AND n.node_type = ?
                  AND s.client_initialized = 1
                """,
                (NodeType.dynamic.value,),
            ).fetchall()
        return [{"config_id": str(row["config_id"]), "node_id": str(row["node_id"])} for row in rows]

    def record_client_heartbeat(
        self,
        config_id: str,
        node_id: str,
        *,
        boot_id: str = "",
        session_id: str = "",
        client_online: bool = True,
        wg_online: bool = False,
    ) -> dict[str, object]:
        node = self.get_node(node_id)
        if node.node_type != NodeType.dynamic:
            return self.get_client_state(config_id, node_id)
        now = now_utc().isoformat()
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            connection.execute(
                """
                UPDATE node_client_state
                SET client_presence_state = 'online',
                    boot_id = COALESCE(NULLIF(?, ''), boot_id),
                    session_id = COALESCE(NULLIF(?, ''), session_id),
                    last_heartbeat_at = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (boot_id, session_id, now, now, config_id, node_id),
            )
            connection.execute(
                """
                UPDATE endpoint_runtime_status
                SET online = ?,
                    connectivity_state = ?,
                    wg_running = ?,
                    wg_runtime_state = ?,
                    heartbeat_client_online = ?,
                    heartbeat_wg_online = ?,
                    last_seen = ?,
                    last_connectivity_reason = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (
                    int(client_online),
                    ConnectivityState.online.value if client_online else ConnectivityState.offline.value,
                    int(wg_online),
                    WgRuntimeState.running.value if wg_online else WgRuntimeState.stopped.value,
                    int(client_online),
                    int(wg_online),
                    now if client_online else None,
                    "client-heartbeat",
                    now,
                    config_id,
                    node_id,
                ),
            )
        return self.get_client_state(config_id, node_id)

    def record_client_event(
        self,
        config_id: str,
        node_id: str,
        *,
        event: str,
        message: str = "",
        boot_id: str = "",
        session_id: str = "",
    ) -> dict[str, object]:
        node = self.get_node(node_id)
        if node.node_type != NodeType.dynamic:
            return self.get_client_state(config_id, node_id)
        now = now_utc().isoformat()
        presence = "offline" if event == "offline" else "online"
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            connection.execute(
                """
                UPDATE node_client_state
                SET client_presence_state = ?,
                    boot_id = COALESCE(NULLIF(?, ''), boot_id),
                    session_id = COALESCE(NULLIF(?, ''), session_id),
                    last_will_at = CASE WHEN ? = 'offline' THEN ? ELSE last_will_at END,
                    last_event = ?,
                    last_event_at = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (presence, boot_id, session_id, event, now, f"{event}: {message}".strip(": "), now, now, config_id, node_id),
            )
            if event == "offline":
                connection.execute(
                    """
                    UPDATE endpoint_runtime_status
                    SET online = 0,
                        connectivity_state = ?,
                        last_connectivity_reason = ?,
                        updated_at = ?
                    WHERE config_id = ? AND node_id = ?
                    """,
                    (ConnectivityState.offline.value, "client-will-message", now, config_id, node_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE endpoint_runtime_status
                    SET online = 1,
                        connectivity_state = ?,
                        last_seen = ?,
                        last_connectivity_reason = ?,
                        updated_at = ?
                    WHERE config_id = ? AND node_id = ?
                    """,
                    (ConnectivityState.online.value, now, f"client-event:{event}", now, config_id, node_id),
                )
        return self.get_client_state(config_id, node_id)

    def record_detect_sent(self, config_id: str, node_id: str) -> None:
        now = now_utc().isoformat()
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            connection.execute(
                """
                UPDATE endpoint_runtime_status
                SET connectivity_state = ?,
                    last_probe_sent_at = ?,
                    last_connectivity_reason = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (ConnectivityState.probing.value, now, "detect-sent", now, config_id, node_id),
            )

    def record_detect_timeout(self, config_id: str, node_id: str) -> None:
        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute(
                """
                UPDATE endpoint_runtime_status
                SET online = 0,
                    connectivity_state = ?,
                    wg_running = 0,
                    wg_runtime_state = ?,
                    detect_client_online = 0,
                    detect_wg_online = 0,
                    last_connectivity_reason = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (ConnectivityState.offline.value, WgRuntimeState.stopped.value, "detect-timeout", now, config_id, node_id),
            )

    def record_detect_ack(
        self,
        config_id: str,
        node_id: str,
        *,
        boot_id: str = "",
        session_id: str = "",
        client_online: bool = True,
        wg_online: bool = False,
    ) -> dict[str, object]:
        node = self.get_node(node_id)
        if node.node_type != NodeType.dynamic:
            return self.get_client_state(config_id, node_id)
        now = now_utc().isoformat()
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            connection.execute(
                """
                UPDATE node_client_state
                SET client_presence_state = 'online',
                    boot_id = COALESCE(NULLIF(?, ''), boot_id),
                    session_id = COALESCE(NULLIF(?, ''), session_id),
                    last_detect_ack_at = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (boot_id, session_id, now, now, config_id, node_id),
            )
            connection.execute(
                """
                UPDATE endpoint_runtime_status
                SET online = ?,
                    connectivity_state = ?,
                    wg_running = ?,
                    wg_runtime_state = ?,
                    detect_client_online = ?,
                    detect_wg_online = ?,
                    last_seen = ?,
                    last_probe_ack_at = ?,
                    last_connectivity_reason = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (
                    int(client_online),
                    ConnectivityState.online.value if client_online else ConnectivityState.offline.value,
                    int(wg_online),
                    WgRuntimeState.running.value if wg_online else WgRuntimeState.stopped.value,
                    int(client_online),
                    int(wg_online),
                    now if client_online else None,
                    now,
                    "detect-ack",
                    now,
                    config_id,
                    node_id,
                ),
            )
        return self.get_client_state(config_id, node_id)
