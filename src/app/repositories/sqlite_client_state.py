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

    def mark_client_bound(self, config_id: str, node_id: str, *, username: str, client_id: str) -> dict[str, object]:
        now = now_utc().isoformat()
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            connection.execute(
                """
                UPDATE node_client_state
                SET client_initialized = 1,
                    mqtt_username = ?,
                    mqtt_client_id = ?,
                    bind_token_used_at = ?,
                    client_presence_state = 'offline',
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (username, client_id, now, now, config_id, node_id),
            )
        return self.get_client_state(config_id, node_id)

    def reset_client_state(self, config_id: str, node_id: str) -> dict[str, object]:
        self._ensure_client_state(config_id, node_id)
        with connect() as connection:
            self._reset_client_state_row(connection, config_id, node_id)
            self._reset_runtime_row(connection, config_id, node_id, reason="client-reset", clear_downloaded=True)
        return self.get_client_state(config_id, node_id)

    def record_client_heartbeat(self, config_id: str, node_id: str, *, boot_id: str = "", session_id: str = "") -> dict[str, object]:
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
                SET online = 1,
                    connectivity_state = ?,
                    last_seen = ?,
                    last_connectivity_reason = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (ConnectivityState.online.value, now, "client-heartbeat", now, config_id, node_id),
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

    def record_detect_ack(self, config_id: str, node_id: str, *, boot_id: str = "", session_id: str = "") -> dict[str, object]:
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
                SET online = 1,
                    connectivity_state = ?,
                    last_seen = ?,
                    last_probe_ack_at = ?,
                    last_connectivity_reason = ?,
                    updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (ConnectivityState.online.value, now, now, "detect-ack", now, config_id, node_id),
            )
        return self.get_client_state(config_id, node_id)
