from __future__ import annotations

from typing import cast

from app.domain.models import Config, ConfigSyncState, Node, NodeType


class ConfigOverviewProjection:
    def project(
        self,
        config: Config,
        nodes: list[Node],
        runtimes: list[dict[str, object]],
        peer_link_count: int,
        sync_status: object,
        topology: dict[str, object],
    ) -> dict[str, object]:
        invalid_node_ids = set(cast(list[str], topology.get("invalid_node_ids", [])))
        runtime_by_node_id = {str(item["node_id"]): item for item in runtimes}
        dynamic_node_ids = {node.id for node in nodes if node.node_type == NodeType.dynamic}
        return {
            "config": config,
            "stats": {
                "total_nodes": len(nodes),
                "dynamic_nodes": len([node for node in nodes if node.node_type == NodeType.dynamic]),
                "static_nodes": len([node for node in nodes if node.node_type == NodeType.static]),
                "online_nodes": len(
                    [item for item in runtimes if str(item["node_id"]) in dynamic_node_ids and bool(item["online"])]
                ),
                "pending_sync_nodes": len(
                    [
                        item
                        for item in runtimes
                        if str(item["node_id"]) in dynamic_node_ids
                        and str(item["config_sync_state"]) != ConfigSyncState.in_sync.value
                    ]
                ),
                "peer_links": peer_link_count,
            },
            "nodes": nodes,
            "node_cards": [
                {
                    "id": node.id,
                    "name": node.name,
                    "node_type": node.node_type,
                    "virtual_ip": node.virtual_ip,
                    "ipv4_address": node.ipv4_address,
                    "ipv6_address": node.ipv6_address,
                    "tags": node.tags,
                    "created_at": node.created_at.isoformat(),
                    "online": node.node_type == NodeType.dynamic and bool(runtime_by_node_id.get(node.id, {}).get("online", False)),
                    "peers_total": cast(int, runtime_by_node_id.get(node.id, {}).get("peers_total", 0) or 0),
                    "mesh_error": node.id in invalid_node_ids,
                }
                for node in nodes
            ],
            "runtime_snapshot": runtimes,
            "sync_status": sync_status,
            "topology": topology,
        }


config_overview_projection = ConfigOverviewProjection()
