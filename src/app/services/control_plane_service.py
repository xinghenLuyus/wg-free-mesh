from __future__ import annotations

import asyncio
import ssl
import logging
from time import perf_counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AppError
from app.domain.models import ControlStatus, NodeType
from app.events.publish_plan import PublishPlan
from app.events.realtime_publisher import RealtimePublisher
from app.repositories.naming import node_config_interface_name
from app.repositories.sqlite import store
from app.services.config_projection_service import ConfigProjectionSnapshot, config_projection_service
from app.services.realtime_service import realtime_service
from app.services.snapshot_service import snapshot_service
from app.services.system_projection_service import system_projection_service

logger = logging.getLogger(__name__)


def _dump_model(value: object) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return {}


def _iso_datetime(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


class ControlPlaneService:
    def __init__(self) -> None:
        self.publisher = RealtimePublisher(self)
        self._refresh_queue: asyncio.Queue[str] | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_lock = asyncio.Lock()
        self._pending_refresh_plans: dict[str, PublishPlan] = {}
        self._queued_refresh_ids: set[str] = set()
        self._running_refresh_ids: set[str] = set()
        self._config_projection_cache: dict[str, ConfigProjectionSnapshot] = {}

    def startup(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_queue = asyncio.Queue()
        self._pending_refresh_plans.clear()
        self._queued_refresh_ids.clear()
        self._running_refresh_ids.clear()
        self._config_projection_cache.clear()
        self._refresh_task = asyncio.create_task(self._refresh_worker(), name="config-refresh-worker")

    async def shutdown(self) -> None:
        task = self._refresh_task
        self._refresh_task = None
        self._refresh_queue = None
        self._pending_refresh_plans.clear()
        self._queued_refresh_ids.clear()
        self._running_refresh_ids.clear()
        self._config_projection_cache.clear()
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _merge_publish_plan(self, target: PublishPlan, incoming: PublishPlan) -> None:
        target.refresh_configs = target.refresh_configs or incoming.refresh_configs
        target.refresh_system_status = target.refresh_system_status or incoming.refresh_system_status
        target.config_overview_ids.update(incoming.config_overview_ids)
        target.node_workspaces.update(incoming.node_workspaces)
        target.node_applies.update(incoming.node_applies)
        target.mesh_workspaces.update(incoming.mesh_workspaces)

    async def _refresh_worker(self) -> None:
        assert self._refresh_queue is not None
        while True:
            config_id = await self._refresh_queue.get()
            async with self._refresh_lock:
                self._queued_refresh_ids.discard(config_id)
                plan = self._pending_refresh_plans.pop(config_id, PublishPlan())
                self._running_refresh_ids.add(config_id)
            try:
                await asyncio.to_thread(store.refresh_config_state, config_id)
                await self.publish_pending_config_pushes(config_id, requested_by="auto-sync")
                snapshot = await asyncio.to_thread(config_projection_service.build, config_id)
                self._config_projection_cache[config_id] = snapshot
                await self.publish_plan(
                    plan,
                    config_snapshots={config_id: snapshot},
                    system_status_payload=self.system_status(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("config refresh worker failed for %s", config_id)
            finally:
                async with self._refresh_lock:
                    self._running_refresh_ids.discard(config_id)
                    should_requeue = config_id in self._pending_refresh_plans and self._refresh_queue is not None
                    if should_requeue and config_id not in self._queued_refresh_ids:
                        self._queued_refresh_ids.add(config_id)
                        await self._refresh_queue.put(config_id)

    async def schedule_config_refresh(self, config_id: str, plan: PublishPlan) -> None:
        self.invalidate_config_projection(config_id)
        if self._refresh_queue is None or self._refresh_task is None or self._refresh_task.done():
            await asyncio.to_thread(store.refresh_config_state, config_id)
            await self.publish_pending_config_pushes(config_id, requested_by="auto-sync")
            snapshot = await asyncio.to_thread(config_projection_service.build, config_id)
            self._config_projection_cache[config_id] = snapshot
            await self.publish_plan(
                plan,
                config_snapshots={config_id: snapshot},
                system_status_payload=self.system_status(),
            )
            return
        async with self._refresh_lock:
            existing = self._pending_refresh_plans.get(config_id)
            if existing is None:
                existing = PublishPlan()
                self._pending_refresh_plans[config_id] = existing
            self._merge_publish_plan(existing, plan)
            if config_id not in self._queued_refresh_ids and config_id not in self._running_refresh_ids:
                self._queued_refresh_ids.add(config_id)
                await self._refresh_queue.put(config_id)

    def invalidate_config_projection(self, config_id: str) -> None:
        self._config_projection_cache.pop(config_id, None)

    def _config_refresh_in_flight(self, config_id: str) -> bool:
        return config_id in self._pending_refresh_plans or config_id in self._queued_refresh_ids or config_id in self._running_refresh_ids

    def _build_config_projection(self, config_id: str, *, use_cache: bool = True, store_cache: bool = True) -> ConfigProjectionSnapshot:
        if use_cache:
            cached = self._config_projection_cache.get(config_id)
            if cached is not None:
                return cached
        snapshot = config_projection_service.build(config_id)
        if store_cache:
            self._config_projection_cache[config_id] = snapshot
        return snapshot

    def _serialize_config_projection(self, snapshot: ConfigProjectionSnapshot) -> dict[str, Any]:
        overview = snapshot.overview.copy()
        overview["config"] = _dump_model(overview["config"])
        nodes = overview.get("nodes", [])
        overview["nodes"] = [_dump_model(item) for item in nodes] if isinstance(nodes, list) else []
        runtime_snapshot = overview.get("runtime_snapshot", [])
        if isinstance(runtime_snapshot, list):
            overview["runtime_snapshot"] = [
                {
                    **item,
                    "last_seen": _iso_datetime(item.get("last_seen")),
                    "last_probe_sent_at": _iso_datetime(item.get("last_probe_sent_at")),
                    "last_probe_ack_at": _iso_datetime(item.get("last_probe_ack_at")),
                }
                for item in runtime_snapshot
                if isinstance(item, dict)
            ]
        return {"config_id": snapshot.config_id, "overview": overview, "tags": snapshot.tags}

    def configs_payload(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self.list_configs()]

    def node_workspace(self, config_id: str, node_id: str) -> dict[str, Any]:
        config = next((item for item in self.list_configs() if item.id == config_id), None)
        try:
            endpoint_status = self.endpoint_status(config_id, node_id)
        except AppError as exc:
            if exc.code != "NODE_DISABLED":
                raise
            endpoint_status = None
        return {
            "config": config.model_dump(mode="json") if config else None,
            "node": self.get_node(node_id).model_dump(mode="json"),
            "endpoint_status": endpoint_status,
            "tags": self.list_tags(config_id),
        }

    def node_apply(self, config_id: str, node_id: str) -> dict[str, Any]:
        node = self.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint has no config apply workspace", 409)
        return {
            "config_id": config_id,
            "node_id": node_id,
            "sync_status": self.sync_status_for_node(config_id, node_id),
            "preview": self.build_wg_preview(config_id, node_id),
            "applied": self.read_applied_conf(config_id, node_id),
        }

    def snapshots_payload(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self.list_snapshots()]

    def peer_link_group_context(self, group_id: str) -> tuple[str, set[str]]:
        for config in self.list_configs():
            links = [item for item in self.list_peer_links(config.id) if item.link_group_id == group_id]
            if links:
                return config.id, {item.local_node_id for item in links}
        raise AppError("PEER_LINK_NOT_FOUND", "Peer link group not found", 404)

    async def publish_configs(self) -> None:
        await realtime_service.publish("config.list.updated", {"configs": self.configs_payload()})

    async def publish_system_status(self) -> None:
        await realtime_service.publish("system.status.updated", self.system_status())

    async def publish_system_status_payload(self, payload: dict[str, object]) -> None:
        await realtime_service.publish("system.status.updated", payload)

    async def publish_config_overview(self, config_id: str) -> None:
        snapshot = self._build_config_projection(config_id, use_cache=False, store_cache=True)
        await self.publish_config_overview_snapshot(snapshot)

    async def publish_config_overview_snapshot(self, snapshot: ConfigProjectionSnapshot) -> None:
        await realtime_service.publish("config.overview.updated", self._serialize_config_projection(snapshot))

    async def publish_node_workspace(self, config_id: str, node_id: str) -> None:
        await realtime_service.publish(
            "node.workspace.updated",
            {
                "config_id": config_id,
                "node_id": node_id,
                "workspace": self.node_workspace(config_id, node_id),
            },
        )

    async def publish_node_apply(self, config_id: str, node_id: str) -> None:
        try:
            payload = self.node_apply(config_id, node_id)
        except AppError as exc:
            if exc.code != "NODE_DISABLED":
                raise
            return
        await realtime_service.publish("node.apply.updated", payload)

    async def publish_mesh_workspace(self, config_id: str, node_id: str) -> None:
        await realtime_service.publish(
            "mesh.workspace.updated",
            {
                "config_id": config_id,
                "node_id": node_id,
                "workspace": self.mesh_workspace(config_id, node_id),
                "nodes": [item.model_dump(mode="json") for item in self.list_nodes(config_id)],
            },
        )

    async def publish_mqtt_settings(self) -> None:
        await realtime_service.publish("settings.mqtt.updated", {"mqtt": self.mqtt_settings()})

    async def publish_snapshots(self) -> None:
        await realtime_service.publish("snapshot.list.updated", {"snapshots": self.snapshots_payload()})

    async def publish_full_state(self) -> None:
        await self.publish_configs()
        await self.publish_system_status()
        await self.publish_snapshots()
        for config in self.list_configs():
            await self.publish_config_overview(config.id)
            for node in self.list_nodes(config.id):
                await self.publish_node_workspace(config.id, node.id)
                if node.enabled:
                    await self.publish_node_apply(config.id, node.id)
                await self.publish_mesh_workspace(config.id, node.id)

    def plan_for_mesh_change(self, config_id: str, affected_node_ids: list[str] | set[str]) -> PublishPlan:
        plan = PublishPlan(refresh_configs=True, refresh_system_status=True)
        plan.add_config_overview(config_id)
        for node_id in affected_node_ids:
            plan.add_node_scope(config_id, str(node_id))
        return plan

    def plan_for_config_change(
        self,
        config_id: str,
        affected_node_ids: list[str] | set[str] | None = None,
        include_overview: bool = True,
    ) -> PublishPlan:
        plan = PublishPlan(refresh_configs=True, refresh_system_status=True)
        if include_overview:
            plan.add_config_overview(config_id)
        for node_id in affected_node_ids or []:
            plan.add_node_scope(config_id, str(node_id))
        return plan

    def plan_for_node_change(self, config_id: str, affected_node_ids: list[str] | set[str]) -> PublishPlan:
        plan = PublishPlan(refresh_configs=True, refresh_system_status=True)
        plan.add_config_overview(config_id)
        for node_id in affected_node_ids:
            plan.add_node_scope(config_id, str(node_id))
        return plan

    async def publish_plan(
        self,
        plan: PublishPlan,
        *,
        config_snapshots: dict[str, ConfigProjectionSnapshot] | None = None,
        system_status_payload: dict[str, object] | None = None,
    ) -> None:
        await self.publisher.publish(plan, config_snapshots=config_snapshots, system_status_payload=system_status_payload)

    async def publish_runtime(self, config_id: str, node_id: str) -> None:
        try:
            status = self.endpoint_status(config_id, node_id)
        except AppError as exc:
            if exc.code != "NODE_DISABLED":
                raise
            status = None
        await realtime_service.publish("endpoint.status.updated", {"config_id": config_id, "node_id": node_id, "status": status})
        snapshot = self._build_config_projection(config_id, use_cache=False, store_cache=True)
        await realtime_service.publish("runtime.snapshot.updated", {"config_id": config_id, "items": snapshot.overview["runtime_snapshot"]})
        await realtime_service.publish("system.status.updated", self.system_status())

    async def publish_runtime_scope(self, config_id: str, node_id: str) -> None:
        await self.publish_runtime(config_id, node_id)

    def create_config(self, payload: dict[str, object]):
        return store.create_config(payload)

    def update_config(self, config_id: str, payload: dict[str, object]):
        self.invalidate_config_projection(config_id)
        return store.update_config(config_id, payload)

    def delete_config(self, config_id: str) -> None:
        store.delete_config(config_id)
        self.invalidate_config_projection(config_id)

    def list_configs(self):
        return store.list_configs()

    def get_config(self, config_id: str):
        return store.get_config(config_id)

    def config_overview(self, config_id: str):
        use_cache = not self._config_refresh_in_flight(config_id)
        snapshot = self._build_config_projection(config_id, use_cache=use_cache, store_cache=use_cache)
        return self._serialize_config_projection(snapshot)["overview"]

    def list_nodes(self, config_id: str):
        return store.list_nodes(config_id)

    def get_node(self, node_id: str):
        return store.get_node(node_id)

    def create_node(self, config_id: str, payload: dict[str, object]):
        self.invalidate_config_projection(config_id)
        return store.create_node(config_id, payload)

    def update_node(self, node_id: str, payload: dict[str, object]):
        previous = store.get_node(node_id)
        self.invalidate_config_projection(previous.config_id)
        result = store.update_node(node_id, payload)
        current = store.get_node(node_id)
        if previous.node_type != current.node_type:
            if current.node_type == NodeType.static:
                from app.services.emqx_service import emqx_service

                try:
                    emqx_service.delete_node_user(node_id=node_id)
                except Exception:
                    pass
            store.reconcile_node_operational_state(current.config_id, current.id)
        return result

    def list_tags(self, config_id: str):
        return store.list_tags(config_id)

    def create_tag(self, config_id: str, tag: str):
        self.invalidate_config_projection(config_id)
        return store.create_tag(config_id, tag)

    def apply_tag_to_nodes(self, config_id: str, tag: str, node_ids: list[str]):
        self.invalidate_config_projection(config_id)
        return store.apply_tag_to_nodes(config_id, tag, node_ids)

    def replace_node_tags(self, node_id: str, tags: list[str]):
        config_id = store.get_node(node_id).config_id
        self.invalidate_config_projection(config_id)
        return store.replace_node_tags(node_id, tags)

    def remove_tag_from_node(self, node_id: str, tag: str):
        config_id = store.get_node(node_id).config_id
        self.invalidate_config_projection(config_id)
        return store.remove_tag_from_node(node_id, tag)

    def delete_tag_from_config(self, config_id: str, tag: str):
        self.invalidate_config_projection(config_id)
        return store.delete_tag_from_config(config_id, tag)

    def delete_node(self, node_id: str) -> None:
        node = store.get_node(node_id)
        self.invalidate_config_projection(node.config_id)
        store.delete_node(node_id)

    def suggest_virtual_ip(self, config_id: str):
        return store.suggest_virtual_ip(config_id)

    def validate_virtual_ip(self, config_id: str, value: str):
        return store.validate_virtual_ip(config_id, value)

    def create_keys(self):
        return store.create_keys()

    def create_preshared_key(self):
        return store.create_preshared_key()

    def derive_public_key(self, private_key: str):
        return store.derive_public_key_from_private(private_key)

    def list_peer_links(self, config_id: str):
        return store.list_peer_links(config_id)

    def mesh_workspace(self, config_id: str, node_id: str):
        return store.mesh_workspace(config_id, node_id)

    def build_peer_link_draft(self, config_id: str, node_id: str, peer_node_id: str, endpoint_ref_family: str):
        return store.build_peer_link_draft(config_id, node_id, peer_node_id, endpoint_ref_family)

    def create_peer_link_group(self, config_id: str, payload: dict[str, object]):
        self.invalidate_config_projection(config_id)
        return store.create_peer_link_group(config_id, payload)

    def update_peer_link_group(self, group_id: str, payload: dict[str, object]):
        config_id, _ = self.peer_link_group_context(group_id)
        self.invalidate_config_projection(config_id)
        return store.update_peer_link_group(group_id, payload)

    def delete_peer_link_group(self, group_id: str) -> None:
        config_id, _ = self.peer_link_group_context(group_id)
        self.invalidate_config_projection(config_id)
        store.delete_peer_link_group(group_id)

    def validate_mesh(self, config_id: str) -> dict[str, object]:
        return store._validate_mesh_payload(config_id)

    def build_wg_preview(self, config_id: str, node_id: str):
        return store.build_wg_preview(config_id, node_id)

    def read_applied_conf(self, config_id: str, node_id: str):
        return store.read_applied_conf(config_id, node_id)

    def download_package(self, config_id: str, node_id: str):
        return store.download_package(config_id, node_id)

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
            {**item, "last_seen": _iso_datetime(item["last_seen"]),
             "last_probe_sent_at": _iso_datetime(item["last_probe_sent_at"]),
             "last_probe_ack_at": _iso_datetime(item["last_probe_ack_at"])}
            for item in items
        ]

    def endpoint_status(self, config_id: str, node_id: str):
        status = store.get_node_endpoint_status(config_id, node_id)
        return {
            "node": _dump_model(status["node"]),
            "runtime": _dump_model(status["runtime"]),
            "client_state": status["client_state"],
            "mqtt_service": self.mqtt_service_status(),
            "config_state": status["config_state"],
            "last_control": _dump_model(status["last_control"]) if status["last_control"] else None,
        }

    def create_client_bind_command(self, config_id: str, node_id: str, server_url: str) -> dict[str, object]:
        if not self.mqtt_service_enabled():
            raise AppError("MQTT_DISABLED", "MQTT services are disabled", 409)
        grant = store.create_client_bind_token(config_id, node_id)
        token = str(grant["token"])
        command = f'wfmctl bind --server "{server_url.rstrip("/")}" --token "{token}"'
        return {
            "command": command,
            "token": token,
            "expires_at": _iso_datetime(grant["expires_at"]) or "",
        }

    def client_bind_preview(self, token: str) -> dict[str, object]:
        return store.validate_client_bind_token(token)

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
        return store.mark_client_bound(
            config_id,
            node_id,
            username=username,
            client_id=client_id,
            platform=platform,
            version=version,
            hostname=hostname,
        )

    def reset_client_state(self, config_id: str, node_id: str) -> dict[str, object]:
        return store.reset_client_state(config_id, node_id)

    def endpoint_logs(self, config_id: str, node_id: str):
        return [item.model_dump(mode="json") for item in store.list_endpoint_logs(config_id, node_id)]

    def _config_push_payload_body(self, config_id: str, node_id: str) -> dict[str, object]:
        config = store.get_config(config_id)
        node = store.get_node(node_id)
        if not node.enabled:
            raise AppError("NODE_DISABLED", "Disabled endpoint cannot receive config push", 409)
        state = store.get_node_config_state(config_id, node_id)
        if not state.staged_text or not state.staged_sha256:
            raise AppError("NO_STAGED_CONFIG", "No staged config to push", 409)
        return {
            "action": "push_config",
            "interface_name": node_config_interface_name(config.name, node.name),
            "config_version": state.staged_version,
            "config_sha256": state.staged_sha256,
            "config_text": state.staged_text,
        }

    async def publish_config_push(self, config_id: str, node_id: str, *, requested_by: str = "admin"):
        from app.services.mqtt_ingress_service import mqtt_ingress_service

        log = store.create_control_log(config_id, node_id, "push_config", requested_by=requested_by)
        await realtime_service.publish("control.log.created", {"config_id": config_id, "node_id": node_id, "log": log.model_dump(mode="json")})
        try:
            payload_body = self._config_push_payload_body(config_id, node_id)
        except AppError as exc:
            updated_log = store.complete_control_log(log.request_id, ControlStatus.failed, exc.message)
            await realtime_service.publish("control.log.updated", {"config_id": config_id, "node_id": node_id, "log": updated_log.model_dump(mode="json")})
            raise
        payload = {
            "type": "config/push",
            "request_id": log.request_id,
            "config_id": config_id,
            "node_id": node_id,
            "boot_id": "",
            "session_id": "",
            "sent_at": datetime.now(UTC).isoformat(),
            "payload": payload_body,
        }
        try:
            await mqtt_ingress_service.publish_to_node(config_id=config_id, node_id=node_id, kind="config/push", payload=payload)
        except Exception as exc:
            updated_log = store.complete_control_log(log.request_id, ControlStatus.failed, "MQTT config push failed", str(exc))
            await realtime_service.publish("control.log.updated", {"config_id": config_id, "node_id": node_id, "log": updated_log.model_dump(mode="json")})
            raise AppError("MQTT_CONTROL_UNAVAILABLE", "MQTT control channel is unavailable", 503, {"detail": str(exc)}) from exc
        return {"request_id": log.request_id, "message": "Config push sent over MQTT"}

    async def publish_pending_config_pushes(self, config_id: str, node_ids: list[str] | set[str] | None = None, *, requested_by: str = "auto-sync") -> None:
        if not self.mqtt_service_enabled():
            return
        target_node_ids = {str(node_id) for node_id in node_ids or []}
        for node in store.list_nodes(config_id):
            if target_node_ids and node.id not in target_node_ids:
                continue
            if not node.enabled or node.node_type != NodeType.dynamic:
                continue
            client_state = store.get_client_state(config_id, node.id)
            if not client_state.get("client_initialized"):
                continue
            runtime = store.get_runtime(config_id, node.id)
            if not runtime.online:
                continue
            state = store.get_node_config_state(config_id, node.id)
            if not state.staged_sha256 or state.staged_sha256 == state.confirmed_sha256:
                continue
            try:
                await self.publish_config_push(config_id, node.id, requested_by=requested_by)
            except Exception:
                logger.exception("auto config push failed for %s/%s", config_id, node.id)

    async def control_action(self, config_id: str, node_id: str, action: str):
        if not self.mqtt_service_enabled():
            raise AppError("MQTT_DISABLED", "MQTT services are disabled", 409)
        if action not in {"start", "stop", "push_config", "wg_show"}:
            raise AppError("INVALID_ACTION", "Only start, stop, push_config and wg_show are supported by MQTT control", 400)
        from app.services.mqtt_ingress_service import mqtt_ingress_service

        if action == "push_config":
            return await self.publish_config_push(config_id, node_id)

        log = store.create_control_log(config_id, node_id, action)
        await realtime_service.publish("control.log.created", {"config_id": config_id, "node_id": node_id, "log": log.model_dump(mode="json")})
        kind = "info" if action == "wg_show" else "config/push" if action == "push_config" else "control"
        payload_body: dict[str, object] = {"action": action}
        payload = {
            "type": kind,
            "request_id": log.request_id,
            "config_id": config_id,
            "node_id": node_id,
            "boot_id": "",
            "session_id": "",
            "sent_at": datetime.now(UTC).isoformat(),
            "payload": payload_body,
        }
        try:
            await mqtt_ingress_service.publish_to_node(config_id=config_id, node_id=node_id, kind=kind, payload=payload)
        except Exception as exc:
            updated_log = store.complete_control_log(log.request_id, ControlStatus.failed, "MQTT control publish failed", str(exc))
            await realtime_service.publish("control.log.updated", {"config_id": config_id, "node_id": node_id, "log": updated_log.model_dump(mode="json")})
            raise AppError("MQTT_CONTROL_UNAVAILABLE", "MQTT control channel is unavailable", 503, {"detail": str(exc)}) from exc
        return {"request_id": log.request_id, "message": "Control command sent over MQTT"}

    async def probe_batch(self, config_id: str, node_ids: list[str]):
        from app.services.mqtt_ingress_service import mqtt_ingress_service

        dispatched: list[dict[str, str]] = []
        for node in store.list_nodes(config_id):
            if not node.enabled or node.node_type != "dynamic":
                continue
            if node_ids and node.id not in node_ids:
                continue
            request_id = f"probe-{node.id}-{datetime.now(UTC).timestamp()}"
            asyncio.create_task(mqtt_ingress_service._probe_target(config_id, node.id), name=f"wfm-manual-detect-{node.id}")
            dispatched.append({"node_id": node.id, "request_id": request_id})
        return {"dispatched": dispatched, "skipped": []}

    def mqtt_settings(self):
        mqtt_settings = store.read_setting_json(
            "mqtt_client",
            {
                "host": settings.mqtt_public_host,
                "port": settings.mqtt_bind_port,
                "tls": settings.mqtt_tls_enabled,
            },
        )
        return {
            "host": str(mqtt_settings.get("host") or settings.mqtt_public_host),
            "port": int(str(mqtt_settings.get("port") or settings.mqtt_bind_port)),
            "tls": bool(mqtt_settings.get("tls", settings.mqtt_tls_enabled)),
        }

    def mqtt_service_enabled(self) -> bool:
        return settings.enable_mqtt_services

    def mqtt_service_status(self) -> dict[str, object]:
        from app.services.mqtt_ingress_service import mqtt_ingress_service

        return mqtt_ingress_service.status_summary()

    def read_setting(self, key: str) -> str | None:
        return store.read_setting(key)

    def write_setting(self, key: str, value: str) -> None:
        store.write_setting(key, value)

    def update_mqtt_settings(self, payload: dict[str, object]):
        store.write_setting_json(
            "mqtt_client",
            {
                "host": payload.get("host", settings.mqtt_public_host),
                "port": payload.get("port", settings.mqtt_bind_port),
                "tls": payload.get("tls", settings.mqtt_tls_enabled),
            },
        )
        return self.mqtt_settings()

    async def test_mqtt_settings(self, payload: dict[str, object]) -> dict[str, object]:
        host = str(payload.get("host", "")).strip()
        raw_port = payload.get("port", 0)
        port = int(str(raw_port or 0))
        tls = bool(payload.get("tls", False))

        if not host:
            return {"success": False, "message": "Host is required", "latency_ms": 0}
        if port <= 0:
            return {"success": False, "message": "Port must be greater than 0", "latency_ms": 0}

        started_at = perf_counter()
        writer = None
        try:
            ssl_context: ssl.SSLContext | None = None
            if tls:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=host, port=port, ssl=ssl_context, server_hostname=host if tls else None),
                timeout=3,
            )
            latency_ms = int((perf_counter() - started_at) * 1000)
            message = "TLS handshake succeeded." if tls else "TCP connection succeeded."
            return {"success": True, "message": message, "latency_ms": latency_ms}
        except TimeoutError:
            latency_ms = int((perf_counter() - started_at) * 1000)
            return {"success": False, "message": "Connection timed out.", "latency_ms": latency_ms}
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            detail = str(exc).strip() or exc.__class__.__name__
            return {"success": False, "message": detail, "latency_ms": latency_ms}
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    def update_password(self, current_password: str, new_password: str) -> None:
        store.update_password(current_password, new_password)

    def create_snapshot(self, note: str):
        return snapshot_service.create_snapshot(note)

    def list_snapshots(self):
        return snapshot_service.list_snapshots()

    def get_snapshot_path(self, snapshot_id: str) -> Path:
        return snapshot_service.get_snapshot_path(snapshot_id)

    def export_snapshot(self, snapshot_id: str) -> Path:
        return snapshot_service.export_snapshot(snapshot_id)

    def delete_snapshot(self, snapshot_id: str) -> None:
        snapshot_service.delete_snapshot(snapshot_id)

    def update_snapshot_note(self, snapshot_id: str, note: str):
        return snapshot_service.update_snapshot_note(snapshot_id, note)

    def restore_snapshot(self, snapshot_id: str) -> None:
        snapshot_service.restore_snapshot(snapshot_id)

    def import_snapshot(self, path: Path, original_name: str | None = None):
        return snapshot_service.import_snapshot(path, original_name)

    def system_status(self):
        mqtt_status = self.mqtt_service_status()
        configs = store._list_configs_base()
        snapshots = [self._build_config_projection(config.id, use_cache=True, store_cache=True) for config in configs]
        status = system_projection_service.build(snapshots, mqtt_status=str(mqtt_status["status"]))
        return {**status, "timestamp": _iso_datetime(status["timestamp"]) or ""}


control_plane_service = ControlPlaneService()
