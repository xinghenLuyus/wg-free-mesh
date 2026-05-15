from __future__ import annotations

from collections.abc import Callable
from typing import cast

from app.domain.models import Config, Node, NodeType


class ConfigListProjection:
    def project(
        self,
        configs: list[Config],
        nodes: list[Node],
        runtimes_by_config: dict[str, dict[str, object]],
        states_by_config: dict[str, dict[str, object]],
        topology_for: Callable[[str], dict[str, object]],
    ) -> list[Config]:
        result: list[Config] = []
        nodes_by_config: dict[str, list[Node]] = {}
        for node in nodes:
            nodes_by_config.setdefault(node.config_id, []).append(node)
        for config in configs:
            topology = topology_for(config.id)
            config_nodes = nodes_by_config.get(config.id, [])
            disabled_nodes = [node for node in config_nodes if not node.enabled]
            dynamic_nodes = [node for node in config_nodes if node.enabled and node.node_type == NodeType.dynamic]
            runtime_map = runtimes_by_config.get(config.id, {})
            online_node_count = len(
                [
                    node
                    for node in dynamic_nodes
                    if config.enabled
                    and bool(getattr(runtime_map.get(node.id), "online", False))
                ]
            )
            result.append(
                config.model_copy(
                    update={
                        "online_node_count": online_node_count,
                        "offline_node_count": max(len(dynamic_nodes) - online_node_count, 0),
                        "disabled_node_count": len(disabled_nodes),
                        "topology_invalid": bool(config.enabled) and not bool(topology["valid"]),
                        "topology_error_count": cast(int, topology["error_count"]) if config.enabled else 0,
                    }
                )
            )
        return result


config_list_projection = ConfigListProjection()
