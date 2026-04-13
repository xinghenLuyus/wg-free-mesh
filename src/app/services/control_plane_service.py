from __future__ import annotations

from pathlib import Path

from app.domain.models import ControlStatus
from app.repositories.sqlite import store
from app.services.realtime_service import realtime_service


class ControlPlaneService:
    async def publish_runtime(self, config_id: str, node_id: str) -> None:
        status = store.get_node_endpoint_status(config_id, node_id)
        await realtime_service.publish(
            "runtime.node.updated",
            {
                "config_id": config_id,
                "node_id": node_id,
                "runtime": status["runtime"].model_dump(mode="json"),
                "config_state": status["config_state"],
            },
        )
        await realtime_service.publish(
            "runtime.snapshot.updated",
            {"config_id": config_id, "items": self.runtime_snapshot(config_id)},
        )
        await realtime_service.publish(
            "sync.status.updated",
            {"config_id": config_id, "node_id": node_id, "status": store.get_sync_status_for_node(config_id, node_id)},
        )
        await realtime_service.publish("system.status.updated", store.system_status())

    def create_config(self, payload: dict[str, object]):
        return store.create_config(payload)

    def update_config(self, config_id: str, payload: dict[str, object]):
        return store.update_config(config_id, payload)

    def delete_config(self, config_id: str) -> None:
        store.delete_config(config_id)

    def list_configs(self):
        return store.list_configs()

    def get_config(self, config_id: str):
        return store.get_config(config_id)

    def config_overview(self, config_id: str):
        overview = store.config_overview(config_id)
        overview["config"] = overview["config"].model_dump(mode="json")
        return overview

    def list_nodes(self, config_id: str):
        return store.list_nodes(config_id)

    def get_node(self, node_id: str):
        return store.get_node(node_id)

    def create_node(self, config_id: str, payload: dict[str, object]):
        return store.create_node(config_id, payload)

    def update_node(self, node_id: str, payload: dict[str, object]):
        return store.update_node(node_id, payload)

    def delete_node(self, node_id: str) -> None:
        store.delete_node(node_id)

    def suggest_virtual_ip(self, config_id: str):
        return store.suggest_virtual_ip(config_id)

    def validate_virtual_ip(self, config_id: str, value: str):
        return store.validate_virtual_ip(config_id, value)

    def create_keys(self):
        return store.create_keys()

    def derive_public_key(self, private_key: str):
        return store.derive_public_key_from_private(private_key)

    def list_peer_links(self, config_id: str):
        return store.list_peer_links(config_id)

    def create_peer_link_group(self, config_id: str, payload: dict[str, object]):
        return store.create_peer_link_group(config_id, payload)

    def update_peer_link_group(self, group_id: str, payload: dict[str, object]):
        return store.update_peer_link_group(group_id, payload)

    def delete_peer_link_group(self, group_id: str) -> None:
        store.delete_peer_link_group(group_id)

    def validate_mesh(self, config_id: str) -> dict[str, object]:
        messages: list[str] = []
        links = store.list_peer_links(config_id)
        nodes = {node.id: node for node in store.list_nodes(config_id)}
        if not links:
            messages.append("当前配置还没有任何 peer link。")
        for link in links:
            if link.local_node_id == link.peer_node_id:
                messages.append(f"节点 {link.local_node_id} 存在自连接。")
            if link.peer_node_id not in nodes:
                messages.append(f"链路 {link.id} 指向不存在的节点。")
            if not link.allowed_ips:
                messages.append(f"链路 {link.id} 缺少 allowed_ips。")
        return {"valid": not messages, "messages": messages or ["拓扑校验通过。"]}

    def build_wg_preview(self, config_id: str, node_id: str):
        return store.build_wg_preview(config_id, node_id)

    def read_applied_conf(self, config_id: str, node_id: str):
        return store.read_applied_conf(config_id, node_id)

    def save_applied_conf(self, config_id: str, node_id: str, content: str):
        return store.save_applied_conf(config_id, node_id, content)

    def sync_node(self, config_id: str, node_id: str):
        return store.sync_node(config_id, node_id)

    def sync_all(self, config_id: str):
        return store.sync_all(config_id)

    def sync_status_for_config(self, config_id: str):
        return store.get_sync_status_for_config(config_id)

    def sync_status_for_node(self, config_id: str, node_id: str):
        return store.get_sync_status_for_node(config_id, node_id)

    def runtime_snapshot(self, config_id: str):
        items = store.list_runtime_snapshot(config_id)
        return [
            {**item, "last_seen": item["last_seen"].isoformat() if item["last_seen"] else None,
             "last_probe_sent_at": item["last_probe_sent_at"].isoformat() if item["last_probe_sent_at"] else None,
             "last_probe_ack_at": item["last_probe_ack_at"].isoformat() if item["last_probe_ack_at"] else None}
            for item in items
        ]

    def endpoint_status(self, config_id: str, node_id: str):
        status = store.get_node_endpoint_status(config_id, node_id)
        return {
            "node": status["node"].model_dump(mode="json"),
            "runtime": status["runtime"].model_dump(mode="json"),
            "config_state": status["config_state"],
            "last_control": status["last_control"].model_dump(mode="json") if status["last_control"] else None,
        }

    def endpoint_logs(self, config_id: str, node_id: str):
        return [item.model_dump(mode="json") for item in store.list_endpoint_logs(config_id, node_id)]

    async def control_action(self, config_id: str, node_id: str, action: str):
        log = store.create_control_log(config_id, node_id, action)
        await realtime_service.publish("control.log.created", {"config_id": config_id, "node_id": node_id, "log": log.model_dump(mode="json")})
        result = store.apply_control_action(config_id, node_id, action)
        updated_log = store.complete_control_log(log.request_id, ControlStatus.simulated, str(result["summary"]))
        await realtime_service.publish("control.log.updated", {"config_id": config_id, "node_id": node_id, "log": updated_log.model_dump(mode="json")})
        await self.publish_runtime(config_id, node_id)
        return {"request_id": log.request_id, "message": result["summary"]}

    async def probe_batch(self, config_id: str, node_ids: list[str]):
        dispatched: list[dict[str, str]] = []
        for node in store.list_nodes(config_id):
            if node.node_type != "dynamic":
                continue
            if node_ids and node.id not in node_ids:
                continue
            result = await self.control_action(config_id, node.id, "probe")
            dispatched.append({"node_id": node.id, "request_id": str(result["request_id"])})
        return {"dispatched": dispatched, "skipped": []}

    def mqtt_settings(self):
        return store.read_setting_json(
            "mqtt_client",
            {"host": "", "port": 8883, "tls": True, "username": "", "password": ""},
        )

    def update_mqtt_settings(self, payload: dict[str, object]):
        store.write_setting_json("mqtt_client", payload)
        return self.mqtt_settings()

    def update_password(self, current_password: str, new_password: str) -> None:
        store.update_password(current_password, new_password)

    def create_snapshot(self, note: str):
        return store.create_snapshot(note)

    def list_snapshots(self):
        return store.list_snapshots()

    def get_snapshot_path(self, snapshot_id: str) -> Path:
        return Path(store.get_snapshot(snapshot_id).path)

    def delete_snapshot(self, snapshot_id: str) -> None:
        store.delete_snapshot(snapshot_id)

    def update_snapshot_note(self, snapshot_id: str, note: str):
        return store.update_snapshot_note(snapshot_id, note)

    def restore_snapshot(self, snapshot_id: str) -> None:
        store.restore_snapshot(snapshot_id)

    def restore_uploaded_snapshot(self, path: Path) -> None:
        store.restore_snapshot_archive(path)

    def system_status(self):
        status = store.system_status()
        return {
            **status,
            "timestamp": status["timestamp"].isoformat(),
        }


control_plane_service = ControlPlaneService()
