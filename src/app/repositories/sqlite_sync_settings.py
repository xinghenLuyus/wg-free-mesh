# mypy: disable-error-code=attr-defined
from __future__ import annotations

import json

from app.core.errors import AppError
from app.domain.models import ConfigSyncState, derive_public_key, generate_key_pair, generate_private_key, now_utc, sha256_text
from app.infrastructure.database import connect
from app.projections.config_overview_projection import config_overview_projection
from app.projections.system_status_projection import system_status_projection
from app.repositories.naming import node_config_artifact_stem as _node_config_artifact_stem
from app.repositories.row_mappers import state_from_row as _state_from_row


class SQLiteSyncSettingsMixin:
    def build_wg_preview(self, config_id: str, node_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        node = self.get_node(node_id)
        links = [item for item in self.list_peer_links(config_id) if item.local_node_id == node_id and item.enabled]
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
            peer_node = self.get_node(link.peer_node_id)
            lines.extend(["", f"# Peer: {peer_node.name}", "[Peer]", f"PublicKey = {peer_node.public_key}", f"AllowedIPs = {link.allowed_ips}"])
            if link.preshared_key:
                lines.append(f"PresharedKey = {link.preshared_key}")
            endpoint = self._resolve_endpoint(config, peer_node, link)
            if endpoint:
                lines.append(f"Endpoint = {endpoint}")
            if endpoint and link.persistent_keepalive:
                lines.append(f"PersistentKeepalive = {link.persistent_keepalive}")
        content = "\n".join(lines) + "\n"
        return {"node_id": node_id, "node_name": node.name, "content": content, "sha256": sha256_text(content)}

    def refresh_config_state(self, config_id: str) -> None:
        config = self.get_config(config_id)
        peer_links = self.list_peer_links(config_id)
        nodes = self.list_nodes(config_id)
        mesh_validation = self._validate_mesh_payload(config_id)
        topology_valid = bool(mesh_validation["valid"])
        for node in nodes:
            preview = self.build_wg_preview(config_id, node.id)
            with connect() as connection:
                row = connection.execute("SELECT * FROM node_config_state WHERE node_id = ?", (node.id,)).fetchone()
                state = _state_from_row(row)
                desired_text = str(preview["content"])
                desired_sha = str(preview["sha256"])
                desired_version = state.desired_version + 1 if state.desired_sha256 != desired_sha else state.desired_version
                staged_text = state.staged_text
                staged_sha = state.staged_sha256
                staged_version = state.staged_version
                now = now_utc().isoformat()
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
                peer_total = len([item for item in peer_links if item.local_node_id == node.id and item.enabled])
                peer_online = 0
                for link in peer_links:
                    if link.local_node_id != node.id or not link.enabled:
                        continue
                    if self.get_runtime(config_id, link.peer_node_id).online:
                        peer_online += 1
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
                self._write_service_conf(config_id, node.id, staged_text)

    def get_sync_status_for_config(self, config_id: str) -> list[dict[str, object]]:
        return [self.get_sync_status_for_node(config_id, node.id) for node in self.list_nodes(config_id)]

    def get_sync_status_for_node(self, config_id: str, node_id: str) -> dict[str, object]:
        self.get_config(config_id)
        node = self.get_node(node_id)
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
        self.get_node(node_id)
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
            self.sync_node(config_id, node.id, requested_by="sync-all")
            synced.append(node.id)
        return {"message": "All node configs synced", "synced_count": len(synced), "failed_count": 0, "synced": synced, "failed": []}

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
        configs = self.list_configs()
        nodes = [node for config in configs for node in self.list_nodes(config.id)]
        runtimes = [self.get_runtime(node.config_id, node.id).model_dump(mode="json") for node in nodes]
        return system_status_projection.project(configs, nodes, runtimes, self._topology_issue_summary)

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
            sync_status=self.get_sync_status_for_config(config_id),
            topology=topology,
        )
