from __future__ import annotations

from typing import Any

from app.events.publish_plan import PublishPlan
from app.services.config_projection_service import ConfigProjectionSnapshot


class RealtimePublisher:
    def __init__(self, control_plane: Any) -> None:
        self.control_plane = control_plane

    async def publish(
        self,
        plan: PublishPlan,
        *,
        config_snapshots: dict[str, ConfigProjectionSnapshot] | None = None,
        system_status_payload: dict[str, object] | None = None,
    ) -> None:
        if plan.refresh_system_status:
            if system_status_payload is None:
                await self.control_plane.publish_system_status()
            else:
                await self.control_plane.publish_system_status_payload(system_status_payload)
        if plan.refresh_configs:
            await self.control_plane.publish_configs()
        for config_id in sorted(plan.config_overview_ids):
            snapshot = (config_snapshots or {}).get(config_id)
            if snapshot is None:
                await self.control_plane.publish_config_overview(config_id)
            else:
                await self.control_plane.publish_config_overview_snapshot(snapshot)
        for config_id, node_id in sorted(plan.node_workspaces):
            await self.control_plane.publish_node_workspace(config_id, node_id)
        for config_id, node_id in sorted(plan.node_applies):
            await self.control_plane.publish_node_apply(config_id, node_id)
        for config_id, node_id in sorted(plan.mesh_workspaces):
            await self.control_plane.publish_mesh_workspace(config_id, node_id)
