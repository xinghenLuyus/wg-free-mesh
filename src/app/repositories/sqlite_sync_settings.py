# mypy: disable-error-code=attr-defined
from __future__ import annotations

import json
from collections.abc import Sequence

from app.core.errors import AppError
from app.domain.models import Config, ConfigSyncState, ControlStatus, Node, PeerLink, derive_public_key, generate_key_pair, generate_private_key, now_utc, sha256_text
from app.infrastructure.database import connect
from app.projections.config_overview_projection import config_overview_projection
from app.projections.system_status_projection import system_status_projection
from app.repositories.naming import node_config_artifact_stem as _node_config_artifact_stem
from app.repositories.row_mappers import state_from_row as _state_from_row
from app.services.topology_service import topology_service


class SQLiteSyncSettingsMixin:
    def _build_wg_preview_for_node(
        self,
        config: Config,
        node: Node,
        nodes_by_id: dict[str, Node],
        peer_links_by_local: dict[str, list[PeerLink]],
    ) -> dict[str, object]:
        links = peer_links_by_local.get(node.id, [])
        lines = ["[Interface]", f"PrivateKey = {node.private_key}"]
        if node.virtual_ip:
            lines.append(f"Address = {node.virtual_ip}")
        lines.append(f"ListenPort = {node.listen_port or config.default_listen_port}")
        effective_dns = node.dns or config.default_dns
        if effective_dns:
            lines.append(f"DNS = {effective_dns}")
        effective_mtu = node.mtu or config.default_mtu
        if effective_mtu:
            lines.append(f"MTU = {effective_mtu}")
        for link in links:
            peer_node = nodes_by_id.get(link.peer_node_id)
            if peer_node is None or not peer_node.enabled:
                continue
            lines.extend(["", f"# Peer: {peer_node.name}", "[Peer]", f"PublicKey = {peer_node.public_key}", f"AllowedIPs = {link.allowed_ips}"])
            if link.preshared_key:
                lines.append(f"PresharedKey = {link.preshared_key}")
            endpoint = self._resolve_endpoint(config, peer_node, link)
            if endpoint:
                lines.append(f"Endpoint = {endpoint}")
            if endpoint and link.persistent_keepalive:
                lines.append(f"PersistentKeepalive = {link.persistent_keepalive}")
        content = "\n".join(lines) + "\n"
        return {"node_id": node.id, "node_name": node.name, "content": content, "sha256": sha256_text(content)}

    def _sync_statuses_for_nodes(self, config_id: str, nodes: Sequence[Node]) -> list[dict[str, object]]:
        runtime_map = self._list_runtime_rows(config_id)
        state_map = self._list_node_config_states(config_id)
        mesh_validation = self._validate_mesh_payload(config_id)
        topology_valid = bool(mesh_validation["valid"])
        topology_messages = mesh_validation["errors"] if not topology_valid else mesh_validation["warnings"]
        items: list[dict[str, object]] = []
        for node in nodes:
            state = state_map.get(node.id) or self.get_node_config_state(config_id, node.id)
            runtime = runtime_map.get(node.id) or self.get_runtime(config_id, node.id)
            items.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "node_type": node.node_type,
                    "auto_sync": node.auto_sync,
                    "desired_version": state.desired_version,
                    "staged_version": state.staged_version,
                    "confirmed_version": state.confirmed_version,
                    "desired_sha256": state.desired_sha256,
                    "staged_sha256": state.staged_sha256,
                    "confirmed_sha256": state.confirmed_sha256,
                    "reported_local_sha256": state.reported_local_sha256,
                    "reported_local_version": state.reported_local_version,
                    "status": self._sync_status_from_state(state),
                    "runtime_status": runtime.config_sync_state,
                    "topology_valid": topology_valid,
                    "topology_messages": topology_messages,
                }
            )
        return items

    def build_wg_preview(self, config_id: str, node_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint has no WireGuard preview", 409)
        nodes = self.list_nodes(config_id)
        nodes_by_id = {item.id: item for item in nodes}
        peer_links_by_local: dict[str, list[PeerLink]] = {}
        for link in self.list_peer_links(config_id):
            local = nodes_by_id.get(link.local_node_id)
            peer = nodes_by_id.get(link.peer_node_id)
            if link.enabled and local is not None and local.enabled and peer is not None and peer.enabled:
                peer_links_by_local.setdefault(link.local_node_id, []).append(link)
        return self._build_wg_preview_for_node(config, node, nodes_by_id, peer_links_by_local)

    def refresh_config_state(self, config_id: str) -> None:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        peer_links = self.list_peer_links(config_id)
        nodes_by_id = {node.id: node for node in nodes}
        peer_links_by_local: dict[str, list[PeerLink]] = {}
        for link in peer_links:
            local = nodes_by_id.get(link.local_node_id)
            peer = nodes_by_id.get(link.peer_node_id)
            if link.enabled and local is not None and local.enabled and peer is not None and peer.enabled:
                peer_links_by_local.setdefault(link.local_node_id, []).append(link)
        mesh_validation = topology_service.validate_mesh(config, nodes, peer_links)
        topology_valid = bool(mesh_validation["valid"])
        runtime_map = self._list_runtime_rows(config_id)
        state_map = self._list_node_config_states(config_id)
        now = now_utc().isoformat()
        with connect() as connection:
            for node in nodes:
                if not node.enabled:
                    connection.execute(
                        """
                        UPDATE endpoint_runtime_status
                        SET online = 0, connectivity_state = ?, wg_running = 0, wg_runtime_state = ?,
                            config_sync_state = ?, peers_online = 0, peers_total = 0,
                            heartbeat_client_online = 0, heartbeat_wg_online = 0,
                            detect_client_online = 0, detect_wg_online = 0,
                            last_connectivity_reason = ?, updated_at = ?
                        WHERE node_id = ?
                        """,
                        (
                            "unknown",
                            "unknown",
                            ConfigSyncState.unknown.value,
                            "Node disabled",
                            now,
                            node.id,
                        ),
                    )
                    continue
                preview = self._build_wg_preview_for_node(config, node, nodes_by_id, peer_links_by_local)
                state = state_map.get(node.id)
                if state is None:
                    row = connection.execute("SELECT * FROM node_config_state WHERE node_id = ?", (node.id,)).fetchone()
                    if row is None:
                        continue
                    state = _state_from_row(row)
                desired_text = str(preview["content"])
                desired_sha = str(preview["sha256"])
                desired_version = state.desired_version + 1 if state.desired_sha256 != desired_sha else state.desired_version
                staged_text = state.staged_text
                staged_sha = state.staged_sha256
                staged_version = state.staged_version
                if node.auto_sync and topology_valid:
                    staged_text = desired_text
                    staged_sha = desired_sha
                    staged_version = desired_version
                connection.execute(
                    """
                    UPDATE node_config_state
                    SET desired_text = ?, desired_sha256 = ?, desired_version = ?, desired_generated_at = ?,
                        staged_text = ?, staged_sha256 = ?, staged_version = ?, staged_updated_at = ?, updated_at = ?
                    WHERE node_id = ?
                    """,
                    (
                        desired_text,
                        desired_sha,
                        desired_version,
                        now,
                        staged_text,
                        staged_sha,
                        staged_version,
                        now if node.auto_sync and topology_valid else state.staged_updated_at.isoformat() if state.staged_updated_at else None,
                        now,
                        node.id,
                    ),
                )
                active_links = peer_links_by_local.get(node.id, [])
                peer_total = len(active_links)
                peer_online = len(
                    [
                        link
                        for link in active_links
                        if bool((runtime_map.get(link.peer_node_id) or self.get_runtime(config_id, link.peer_node_id)).online)
                    ]
                )
                connection.execute(
                    """
                    UPDATE endpoint_runtime_status
                    SET peers_total = ?, peers_online = ?, config_sync_state = ?, updated_at = ?
                    WHERE node_id = ?
                    """,
                    (
                        peer_total,
                        peer_online,
                        ConfigSyncState.in_sync.value if staged_sha == desired_sha and desired_sha else ConfigSyncState.pending.value,
                        now,
                        node.id,
                    ),
                )
                self._write_service_conf_if_changed(config_id, node.id, staged_text)

    def get_sync_status_for_config(self, config_id: str) -> list[dict[str, object]]:
        nodes = [node for node in self.list_nodes(config_id) if node.enabled]
        return self._sync_statuses_for_nodes(config_id, nodes)

    def get_sync_status_for_node(self, config_id: str, node_id: str) -> dict[str, object]:
        self.get_config(config_id)
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint has no sync status", 409)
        state = self.get_node_config_state(config_id, node_id)
        runtime = self.get_runtime(config_id, node_id)
        mesh_validation = self._validate_mesh_payload(config_id)
        return {
            "node_id": node.id,
            "node_name": node.name,
            "node_type": node.node_type,
            "auto_sync": node.auto_sync,
            "desired_version": state.desired_version,
            "staged_version": state.staged_version,
            "confirmed_version": state.confirmed_version,
            "desired_sha256": state.desired_sha256,
            "staged_sha256": state.staged_sha256,
            "confirmed_sha256": state.confirmed_sha256,
            "reported_local_sha256": state.reported_local_sha256,
            "reported_local_version": state.reported_local_version,
            "status": self._sync_status_from_state(state),
            "runtime_status": runtime.config_sync_state,
            "topology_valid": bool(mesh_validation["valid"]),
            "topology_messages": mesh_validation["errors"] if not mesh_validation["valid"] else mesh_validation["warnings"],
        }

    def read_applied_conf(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint has no applied config", 409)
        state = self.get_node_config_state(config_id, node_id)
        conf_path = self._conf_path(config_id, node_id)
        content = conf_path.read_text(encoding="utf-8") if conf_path.exists() else state.staged_text or ""
        return {
            "exists": bool(content),
            "content": content,
            "node_name": node.name,
            "node_type": node.node_type,
            "source": "server_applied",
            "desired_version": state.desired_version,
            "staged_version": state.staged_version,
        }

    def download_package(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint cannot download config", 409)
        config = self.get_config(config_id)
        applied = self.read_applied_conf(config_id, node_id)
        file_stem = _node_config_artifact_stem(config.name, node.name)
        return {
            "config_id": config_id,
            "node_id": node_id,
            "config_name": config.name,
            "node_name": node.name,
            "filename": f"{file_stem}.conf",
            "content": applied["content"],
            "download_path": f"/api/v1/configs/{config_id}/nodes/{node_id}/download-conf",
        }

    def save_applied_conf(self, config_id: str, node_id: str, content: str) -> dict[str, object]:
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint cannot save applied config", 409)
        state = self.get_node_config_state(config_id, node_id)
        sha = sha256_text(content)
        version = max(state.staged_version, state.desired_version) + 1
        now = now_utc().isoformat()
        self._write_service_conf(config_id, node_id, content)
        with connect() as connection:
            connection.execute(
                "UPDATE node_config_state SET staged_text = ?, staged_sha256 = ?, staged_version = ?, staged_updated_at = ?, updated_at = ? WHERE node_id = ?",
                (content, sha, version, now, now, node_id),
            )
            connection.execute("UPDATE endpoint_runtime_status SET config_sync_state = ?, updated_at = ? WHERE node_id = ?", (ConfigSyncState.in_sync.value, now, node_id))
        return self.get_sync_status_for_node(config_id, node_id)

    def sync_node(self, config_id: str, node_id: str, requested_by: str = "manual") -> dict[str, object]:
        del requested_by
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint cannot sync config", 409)
        mesh_validation = self._validate_mesh_payload(config_id)
        if not mesh_validation["valid"]:
            raise AppError("TOPOLOGY_INVALID", "Please resolve topology validation before syncing.", 409, {"messages": mesh_validation["errors"]})
        preview = self.build_wg_preview(config_id, node_id)
        result = self.save_applied_conf(config_id, node_id, str(preview["content"]))
        state = self.get_node_config_state(config_id, node_id)
        return {"message": "Node config synced", "staged_version": state.staged_version, "staged_sha256": state.staged_sha256, "sync_status": result}

    def sync_all(self, config_id: str) -> dict[str, object]:
        mesh_validation = self._validate_mesh_payload(config_id)
        if not mesh_validation["valid"]:
            raise AppError("TOPOLOGY_INVALID", "Please resolve topology validation before syncing.", 409, {"messages": mesh_validation["errors"]})
        synced: list[str] = []
        for node in self.list_nodes(config_id):
            if not node.enabled:
                continue
            self.sync_node(config_id, node.id, requested_by="sync-all")
            synced.append(node.id)
        return {"message": "All node configs synced", "synced_count": len(synced), "failed_count": 0, "synced": synced, "failed": []}

    def confirm_config_push(self, request_id: str, status_text: str, message: str = ""):
        with connect() as connection:
            row = connection.execute("SELECT * FROM endpoint_control_logs WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            raise AppError("CONTROL_LOG_NOT_FOUND", "Control log not found", 404)
        config_id = str(row["config_id"])
        node_id = str(row["node_id"])
        state = self.get_node_config_state(config_id, node_id)
        normalized_status = status_text.strip().lower()
        if normalized_status == "applied":
            now = now_utc().isoformat()
            with connect() as connection:
                connection.execute(
                    """
                    UPDATE node_config_state
                    SET confirmed_text = ?, confirmed_sha256 = ?, confirmed_version = ?,
                        reported_local_sha256 = ?, reported_local_version = ?,
                        confirmed_updated_at = ?, updated_at = ?
                    WHERE config_id = ? AND node_id = ?
                    """,
                    (
                        state.staged_text,
                        state.staged_sha256,
                        state.staged_version,
                        state.staged_sha256,
                        state.staged_version,
                        now,
                        now,
                        config_id,
                        node_id,
                    ),
                )
            return self.complete_control_log(request_id, ControlStatus.acked, message or "Config applied by client")
        return self.complete_control_log(request_id, ControlStatus.failed, message or status_text or "Config push failed")

    def read_setting_json(self, key: str, default: dict[str, object]) -> dict[str, object]:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            parsed = json.loads(row["value"])
        except json.JSONDecodeError:
            return default
        return {**default, **parsed}

    def write_setting_json(self, key: str, value: dict[str, object]) -> None:
        now = now_utc().isoformat()
        with connect() as connection:
            exists = connection.execute("SELECT key FROM system_settings WHERE key = ?", (key,)).fetchone()
            if exists is None:
                connection.execute("INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)", (key, json.dumps(value, ensure_ascii=False), now))
            else:
                connection.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (json.dumps(value, ensure_ascii=False), now, key))

    def read_setting(self, key: str) -> str | None:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def write_setting(self, key: str, value: str) -> None:
        now = now_utc().isoformat()
        with connect() as connection:
            exists = connection.execute("SELECT key FROM system_settings WHERE key = ?", (key,)).fetchone()
            if exists is None:
                connection.execute("INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)", (key, value, now))
            else:
                connection.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (value, now, key))

    def delete_setting(self, key: str) -> None:
        with connect() as connection:
            connection.execute("DELETE FROM system_settings WHERE key = ?", (key,))

    def read_password(self) -> str:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = 'auth_password_hash'").fetchone()
        return row["value"] if row else "admin123"

    def update_password(self, current_password: str, new_password: str) -> None:
        if self.read_password() != current_password:
            raise AppError("AUTH_FAILED", "Current password is incorrect", 401)
        with connect() as connection:
            connection.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'auth_password_hash'", (new_password, now_utc().isoformat()))

    def create_keys(self) -> dict[str, str]:
        private_key, public_key = generate_key_pair()
        return {"private_key": private_key, "public_key": public_key}

    def create_preshared_key(self) -> dict[str, str]:
        return {"preshared_key": generate_private_key()}

    def derive_public_key_from_private(self, private_key: str) -> dict[str, str]:
        return {"private_key": private_key, "public_key": derive_public_key(private_key)}

    def system_status(self) -> dict[str, object]:
        configs = self._list_configs_base()
        config_ids = [config.id for config in configs]
        nodes = self._list_nodes_for_configs(config_ids)
        runtime_rows_by_config = self._list_runtime_rows_for_configs(config_ids)
        runtimes = [
            runtime.model_dump(mode="json")
            for config_id in config_ids
            for runtime in runtime_rows_by_config.get(config_id, {}).values()
        ]
        peer_links = self._list_peer_links_for_configs(config_ids)
        topology_by_config = self._topology_summaries_for_prefetched(configs, nodes, peer_links)
        return system_status_projection.project(configs, nodes, runtimes, lambda config_id: topology_by_config.get(config_id, {"valid": True, "errors": [], "error_count": 0, "invalid_node_ids": [], "invalid_node_count": 0}))

    def config_overview(self, config_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        runtimes = self.list_runtime_snapshot(config_id)
        topology = self._topology_issue_summary(config_id)
        return config_overview_projection.project(
            config=config,
            nodes=nodes,
            runtimes=runtimes,
            peer_link_count=len(self.list_peer_links(config_id)) // 2,
            sync_status=self._sync_statuses_for_nodes(config_id, [node for node in nodes if node.enabled]),
            topology=topology,
        )
