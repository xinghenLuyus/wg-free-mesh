"""Read-only, secret-free config topology projection."""

from collections import defaultdict

from app.core.features import effective_node_type
from app.data.store import store
from app.domain.models import now_utc
from app.schemas.mesh import MeshHealthRead
from app.services.runtime_observation_service import endpoint_state, runtime_observation_service
from app.services.topology_service import topology_service


def topology_board(config_id: str) -> dict:
    config = store.get_config(config_id)
    nodes = store.list_nodes(config_id)
    by_id = {node.id: node for node in nodes}
    groups = defaultdict(list)
    links = store.list_peer_links(config_id)
    duplicates = topology_service.duplicate_enabled_group_messages_by_group(nodes, links)
    for link in links:
        groups[link.link_group_id].append(link)
    node_rows = []
    for node in nodes:
        runtime = store.get_runtime(config_id, node.id)
        static = effective_node_type(node) == "static"
        node_rows.append(
            {
                "id": node.id,
                "name": node.name,
                "node_type": effective_node_type(node),
                "enabled": node.enabled,
                "virtual_ip": node.virtual_ip,
                "ipv4_address": node.ipv4_address,
                "ipv6_address": node.ipv6_address,
                "tags": node.tags,
                "endpoint_state": None if static else endpoint_state(runtime),
                "wg_runtime_state": None if static else runtime.wg_runtime_state,
                "config_sync_state": None if static else runtime.config_sync_state,
            }
        )
    connections = []
    issues = []
    for group_id, links in sorted(groups.items()):
        # Identity is stable across names and page viewpoint.
        ids = sorted({value for link in links for value in (link.local_node_id, link.peer_node_id)})
        if len(ids) != 2 or any(nid not in by_id for nid in ids):
            issues.append({"group_id": group_id, "reason": "invalid_group"})
            continue
        a, b = (by_id[nid] for nid in ids)
        forward = [
            link for link in links if link.local_node_id == a.id and link.peer_node_id == b.id
        ]
        reverse = [
            link for link in links if link.local_node_id == b.id and link.peer_node_id == a.id
        ]
        intact = len(links) == 2 and len(forward) == len(reverse) == 1
        validation_errors = list(topology_service.validate_mesh(config, nodes, links)["errors"])
        if group_id in duplicates:
            validation_errors.insert(0, duplicates[group_id])
        if not intact:
            validation_errors.append("Mesh pair has incomplete or conflicting directions.")
        blocked = (
            bool(validation_errors)
            or not config.enabled
            or not a.enabled
            or not b.enabled
            or not all(link.enabled for link in links)
        )
        # Reuse the same decision while retaining both sides and round consistency.
        health = MeshHealthRead.model_validate(
            runtime_observation_service.health(config_id, a, b, blocked, all_observations=True)
        ).model_dump(mode="json")

        def direction(items):
            if len(items) != 1:
                return None
            link = items[0]
            card = store._peer_link_direction_card(
                config, by_id[link.local_node_id], by_id[link.peer_node_id], link
            )
            return {
                key: card[key]
                for key in (
                    "link_id",
                    "local_node_id",
                    "peer_node_id",
                    "allowed_ips",
                    "persistent_keepalive",
                    "endpoint_summary",
                    "endpoint_ref_family",
                )
            }

        connections.append(
            {
                "id": group_id,
                "source": a.id,
                "target": b.id,
                "enabled": all(link.enabled for link in links),
                "integrity": intact,
                "validation_errors": validation_errors,
                "has_preshared_key": any(bool(link.preshared_key) for link in links),
                "forward": direction(forward),
                "reverse": direction(reverse),
                "health": health,
            }
        )
    return {
        "config": {
            "id": config.id,
            "name": config.name,
            "enabled": config.enabled,
            "tunnel_protocol": config.tunnel_protocol,
            "awg_version": config.awg_version,
        },
        "nodes": node_rows,
        "connections": connections,
        "issues": issues,
        "generated_at": now_utc().isoformat(),
    }
