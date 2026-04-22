from __future__ import annotations

from typing import Any

from app.events.publish_plan import PublishPlan


class RealtimePublisher:
    def __init__(self, control_plane: Any) -> None:
        self.control_plane = control_plane

    async def publish(self, plan: PublishPlan) -> None:
        if plan.refresh_configs:
            await self.control_plane.publish_configs()
        for config_id in sorted(plan.config_overview_ids):
            await self.control_plane.publish_config_overview(config_id)
        for config_id, node_id in sorted(plan.node_workspaces):
            await self.control_plane.publish_node_workspace(config_id, node_id)
        for config_id, node_id in sorted(plan.node_applies):
            await self.control_plane.publish_node_apply(config_id, node_id)
        for config_id, node_id in sorted(plan.mesh_workspaces):
            await self.control_plane.publish_mesh_workspace(config_id, node_id)
        if plan.refresh_system_status:
            await self.control_plane.publish_system_status()
