from __future__ import annotations

from collections.abc import Callable
from typing import cast

from app.domain.models import Config, ConfigSyncState, Node, NodeType, now_utc


class SystemStatusProjection:
    def project(
        self,
        configs: list[Config],
        nodes: list[Node],
        runtimes: list[dict[str, object]],
        topology_for: Callable[[str], dict[str, object]],
    ) -> dict[str, object]:
        enabled_config_ids = {config.id for config in configs if config.enabled}
        enabled_dynamic_node_ids = {
            node.id for node in nodes if node.config_id in enabled_config_ids and node.enabled and node.node_type == NodeType.dynamic
        }
        invalid_configs: list[dict[str, object]] = []
        invalid_node_ids: set[str] = set()
        for config in configs:
            if not config.enabled:
                continue
            topology = topology_for(config.id)
            if not bool(topology["valid"]):
                config_invalid_node_ids = cast(list[str], topology["invalid_node_ids"])
                invalid_node_ids.update(config_invalid_node_ids)
                invalid_configs.append(
                    {
                        "config_id": config.id,
                        "config_name": config.name,
                        "error_count": topology["error_count"],
                        "invalid_node_count": topology["invalid_node_count"],
                        "errors": topology["errors"],
                    }
                )
        return {
            "summary": {
                "configs": len(configs),
                "nodes": len(nodes),
                "dynamic_nodes": len([node for node in nodes if node.enabled and node.node_type == NodeType.dynamic]),
                "online_nodes": len(
                    [runtime for runtime in runtimes if str(runtime["node_id"]) in enabled_dynamic_node_ids and bool(runtime["online"])]
                ),
                "pending_sync_nodes": len(
                    [
                        runtime
                        for runtime in runtimes
                        if str(runtime["node_id"]) in enabled_dynamic_node_ids
                        and str(runtime["config_sync_state"]) != ConfigSyncState.in_sync.value
                    ]
                ),
            },
            "topology": {
                "valid": not invalid_configs,
                "invalid_config_count": len(invalid_configs),
                "invalid_node_count": len(invalid_node_ids),
                "invalid_configs": invalid_configs,
            },
            "services": {"database": "ok", "mqtt": "deferred", "wireguard": "deferred"},
            "timestamp": now_utc(),
        }


system_status_projection = SystemStatusProjection()
