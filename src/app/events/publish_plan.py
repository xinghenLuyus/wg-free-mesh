from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PublishPlan:
    refresh_configs: bool = False
    refresh_system_status: bool = False
    config_overview_ids: set[str] = field(default_factory=set)
    node_workspaces: set[tuple[str, str]] = field(default_factory=set)
    node_applies: set[tuple[str, str]] = field(default_factory=set)
    mesh_workspaces: set[tuple[str, str]] = field(default_factory=set)

    def add_config_overview(self, config_id: str) -> None:
        self.config_overview_ids.add(config_id)

    def add_node_scope(self, config_id: str, node_id: str) -> None:
        node_ref = (config_id, node_id)
        self.node_workspaces.add(node_ref)
        self.node_applies.add(node_ref)
        self.mesh_workspaces.add(node_ref)
