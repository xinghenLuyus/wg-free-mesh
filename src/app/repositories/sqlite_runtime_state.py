# mypy: disable-error-code=attr-defined
from __future__ import annotations

from app.core.errors import AppError
from app.domain.models import (
    ConfigSyncState,
    ConnectivityState,
    ControlAction,
    ControlStatus,
    EndpointControlLog,
    EndpointRuntimeStatus,
    NodeType,
    WgRuntimeState,
    now_utc,
)
from app.infrastructure.database import connect
from app.repositories.row_mappers import (
    log_from_row as _log_from_row,
    runtime_from_row as _runtime_from_row,
    state_from_row as _state_from_row,
)
from app.repositories.sqlite_common import control_action_value


class SQLiteRuntimeStateMixin:
    def _trim_endpoint_logs(self, connection: object, config_id: str, node_id: str, limit: int = 20) -> None:
        connection.execute(
            """
            DELETE FROM endpoint_control_logs
            WHERE id IN (
                SELECT id FROM endpoint_control_logs
                WHERE config_id = ? AND node_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (config_id, node_id, limit),
        )

    def get_node_config_state(self, config_id: str, node_id: str):
        with connect() as connection:
            row = connection.execute("SELECT * FROM node_config_state WHERE config_id = ? AND node_id = ?", (config_id, node_id)).fetchone()
        if row is None:
            raise AppError("NODE_STATE_NOT_FOUND", "Node config state not found", 404)
        return _state_from_row(row)

    def get_runtime(self, config_id: str, node_id: str) -> EndpointRuntimeStatus:
        node = self.get_node(node_id)
        with connect() as connection:
            row = connection.execute("SELECT * FROM endpoint_runtime_status WHERE config_id = ? AND node_id = ?", (config_id, node_id)).fetchone()
        if row is None:
            raise AppError("RUNTIME_NOT_FOUND", "Node runtime state not found", 404)
        runtime = _runtime_from_row(row)
        if node.node_type == NodeType.static:
            return runtime.model_copy(
                update={
                    "online": False,
                    "connectivity_state": ConnectivityState.offline,
                    "wg_running": False,
                    "wg_runtime_state": WgRuntimeState.stopped,
                    "last_seen": None,
                    "last_probe_sent_at": None,
                    "last_probe_ack_at": None,
                    "last_control_channel_seen_at": None,
                    "last_connectivity_reason": "static-node",
                    "client_downloaded": False,
                    "client_downloaded_at": None,
                }
            )
        return runtime

    def list_runtime_snapshot(self, config_id: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for node in self.list_nodes(config_id):
            runtime = self.get_runtime(config_id, node.id)
            state = self.get_node_config_state(config_id, node.id)
            client_state = self.get_client_state(config_id, node.id)
            items.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "node_type": node.node_type,
                    "online": runtime.online,
                    "connectivity_state": runtime.connectivity_state,
                    "wg_running": runtime.wg_running,
                    "wg_runtime_state": runtime.wg_runtime_state,
                    "config_sync_state": runtime.config_sync_state,
                    "server_apply_status": self._sync_status_from_state(state),
                    "peers_online": runtime.peers_online,
                    "peers_total": runtime.peers_total,
                    "last_seen": runtime.last_seen,
                    "last_probe_sent_at": runtime.last_probe_sent_at,
                    "last_probe_ack_at": runtime.last_probe_ack_at,
                    "client_initialized": client_state.get("client_initialized", False),
                    "client_presence_state": client_state.get("client_presence_state", "offline"),
                }
            )
        return items

    def list_endpoint_logs(self, config_id: str, node_id: str, limit: int = 50) -> list[EndpointControlLog]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM endpoint_control_logs
                WHERE config_id = ? AND node_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (config_id, node_id, limit),
            ).fetchall()
        return [_log_from_row(row) for row in rows]

    def create_control_log(self, config_id: str, node_id: str, action: str, requested_by: str = "admin") -> EndpointControlLog:
        self.get_node(node_id)
        log = EndpointControlLog(
            config_id=config_id,
            node_id=node_id,
            action=control_action_value(action),
            requested_by=requested_by,
            summary="Command recorded, waiting for server-side simulated execution",
        )
        now = log.created_at.isoformat()
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO endpoint_control_logs
                  (id, request_id, config_id, node_id, action, status, requested_by, summary, detail, requested_at, ack_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.request_id,
                    log.config_id,
                    log.node_id,
                    log.action.value,
                    log.status.value,
                    log.requested_by,
                    log.summary,
                    log.detail,
                    log.requested_at.isoformat(),
                    None,
                    now,
                    now,
                ),
            )
            self._trim_endpoint_logs(connection, config_id, node_id)
        return log

    def append_client_event_log(self, config_id: str, node_id: str, *, summary: str, detail: str = "", requested_by: str = "client") -> EndpointControlLog:
        self.get_node(node_id)
        log = EndpointControlLog(
            config_id=config_id,
            node_id=node_id,
            action=ControlAction.event,
            status=ControlStatus.acked,
            requested_by=requested_by,
            summary=summary,
            detail=detail,
            ack_at=now_utc(),
        )
        created_at = log.created_at.isoformat()
        ack_at = log.ack_at.isoformat() if log.ack_at else None
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO endpoint_control_logs
                  (id, request_id, config_id, node_id, action, status, requested_by, summary, detail, requested_at, ack_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.request_id,
                    log.config_id,
                    log.node_id,
                    log.action.value,
                    log.status.value,
                    log.requested_by,
                    log.summary,
                    log.detail,
                    log.requested_at.isoformat(),
                    ack_at,
                    created_at,
                    created_at,
                ),
            )
            self._trim_endpoint_logs(connection, config_id, node_id)
        return log

    def complete_control_log(self, request_id: str, status: ControlStatus, summary: str, detail: str = "") -> EndpointControlLog:
        with connect() as connection:
            row = connection.execute("SELECT * FROM endpoint_control_logs WHERE request_id = ?", (request_id,)).fetchone()
            if row is None:
                raise AppError("CONTROL_LOG_NOT_FOUND", "Control log not found", 404)
            ack_at = now_utc().isoformat()
            connection.execute(
                """
                UPDATE endpoint_control_logs
                SET status = ?, summary = ?, detail = ?, ack_at = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (status.value, summary, detail, ack_at, ack_at, request_id),
            )
        with connect() as connection:
            final_row = connection.execute("SELECT * FROM endpoint_control_logs WHERE request_id = ?", (request_id,)).fetchone()
        return _log_from_row(final_row)

    def apply_control_action(self, config_id: str, node_id: str, action: str) -> dict[str, object]:
        runtime = self.get_runtime(config_id, node_id)
        now = now_utc()
        updates: dict[str, object] = {
            "updated_at": now.isoformat(),
            "last_control_channel_seen_at": now.isoformat(),
            "last_seen": runtime.last_seen.isoformat() if runtime.last_seen else None,
            "last_probe_sent_at": runtime.last_probe_sent_at.isoformat() if runtime.last_probe_sent_at else None,
            "last_probe_ack_at": runtime.last_probe_ack_at.isoformat() if runtime.last_probe_ack_at else None,
            "last_connectivity_reason": runtime.last_connectivity_reason,
            "online": int(runtime.online),
            "wg_running": int(runtime.wg_running),
            "connectivity_state": runtime.connectivity_state.value,
            "wg_runtime_state": runtime.wg_runtime_state.value,
            "config_sync_state": runtime.config_sync_state.value,
        }
        summary = "Control command recorded"
        if action == ControlAction.probe:
            updates["connectivity_state"] = ConnectivityState.online.value if runtime.online else ConnectivityState.offline.value
            updates["last_probe_sent_at"] = now.isoformat()
            updates["last_probe_ack_at"] = now.isoformat()
            updates["last_connectivity_reason"] = "server-simulated-probe"
            summary = "Probe completed with server-side simulated state"
        elif action == ControlAction.start:
            updates["wg_running"] = 1
            updates["wg_runtime_state"] = WgRuntimeState.running.value
            updates["online"] = 1
            updates["connectivity_state"] = ConnectivityState.online.value
            updates["last_seen"] = now.isoformat()
            summary = "WireGuard marked as running"
        elif action == ControlAction.stop:
            updates["wg_running"] = 0
            updates["wg_runtime_state"] = WgRuntimeState.stopped.value
            updates["online"] = 0
            updates["connectivity_state"] = ConnectivityState.offline.value
            updates["last_connectivity_reason"] = "manual-stop"
            summary = "WireGuard marked as stopped"
        elif action == ControlAction.restart:
            updates["wg_running"] = 1
            updates["wg_runtime_state"] = WgRuntimeState.running.value
            updates["online"] = 1
            updates["connectivity_state"] = ConnectivityState.online.value
            updates["last_seen"] = now.isoformat()
            summary = "WireGuard marked as restarted"
        elif action == ControlAction.sync:
            self.sync_node(config_id, node_id, requested_by="endpoint-control")
            updates["config_sync_state"] = ConfigSyncState.in_sync.value
            summary = "Node config synced to staged state"
        elif action == ControlAction.wg_show:
            summary = "wg_show request recorded, deferred to client phase"
        else:
            raise AppError("INVALID_ACTION", "Unsupported control action", 400)
        with connect() as connection:
            connection.execute(
                """
                UPDATE endpoint_runtime_status
                SET online = ?, connectivity_state = ?, wg_running = ?, wg_runtime_state = ?, config_sync_state = ?,
                    last_seen = ?, last_probe_sent_at = ?, last_probe_ack_at = ?, last_control_channel_seen_at = ?,
                    last_connectivity_reason = ?, updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (
                    updates["online"],
                    updates["connectivity_state"],
                    updates["wg_running"],
                    updates["wg_runtime_state"],
                    updates["config_sync_state"],
                    updates["last_seen"],
                    updates["last_probe_sent_at"],
                    updates["last_probe_ack_at"],
                    updates["last_control_channel_seen_at"],
                    updates["last_connectivity_reason"],
                    updates["updated_at"],
                    config_id,
                    node_id,
                ),
            )
        return {"summary": summary, "runtime": self.get_runtime(config_id, node_id)}

    def get_node_endpoint_status(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        runtime = self.get_runtime(config_id, node_id)
        state = self.get_node_config_state(config_id, node_id)
        logs = self.list_endpoint_logs(config_id, node_id, limit=1)
        return {
            "node": node,
            "runtime": runtime,
            "client_state": self.get_client_state(config_id, node_id),
            "config_state": {
                "desired_version": state.desired_version,
                "staged_version": state.staged_version,
                "confirmed_version": state.confirmed_version,
                "desired_sha256": state.desired_sha256,
                "staged_sha256": state.staged_sha256,
                "confirmed_sha256": state.confirmed_sha256,
                "reported_local_sha256": state.reported_local_sha256,
                "reported_local_version": state.reported_local_version,
                "status": runtime.config_sync_state,
                "server_apply_status": self._sync_status_from_state(state),
            },
            "last_control": logs[0] if logs else None,
        }
