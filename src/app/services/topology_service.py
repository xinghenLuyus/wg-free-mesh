from __future__ import annotations

import ipaddress

from app.domain.models import Config, EndpointMode, EndpointPortMode, Node, PeerLink


def _is_ipv6_literal(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value.strip("[]")), ipaddress.IPv6Address)
    except ValueError:
        return False


class TopologyService:
    def peer_link_groups(self, links: list[PeerLink]) -> dict[str, list[PeerLink]]:
        groups: dict[str, list[PeerLink]] = {}
        for link in links:
            groups.setdefault(link.link_group_id, []).append(link)
        return groups

    def endpoint_host_for_family(self, node: Node, family: object) -> str | None:
        family_value = str(family or "ipv4")
        if family_value == "ipv6":
            return node.ipv6_address
        return node.ipv4_address

    def resolve_endpoint(self, config: Config, peer_node: Node, link: PeerLink) -> str | None:
        if link.endpoint_mode == EndpointMode.none:
            return None
        host = link.endpoint_manual_host if link.endpoint_mode == EndpointMode.manual else self.endpoint_host_for_family(
            peer_node, link.endpoint_ref_family
        )
        if not host:
            return None
        port = (
            link.endpoint_manual_port
            if link.endpoint_port_mode == EndpointPortMode.manual
            else peer_node.listen_port or config.default_listen_port
        )
        if not port:
            return None
        return f"[{host}]:{port}" if _is_ipv6_literal(host) else f"{host}:{port}"

    def link_endpoint_state(self, config: Config, peer_node: Node, link: PeerLink | None) -> str:
        if link is None:
            return "missing"
        if link.endpoint_mode == EndpointMode.none:
            return "disabled"
        return "resolved" if self.resolve_endpoint(config, peer_node, link) else "unresolved"

    def connection_integrity(
        self,
        config: Config,
        local_node: Node,
        peer_node: Node,
        forward: PeerLink | None,
        reverse: PeerLink | None,
    ) -> dict[str, object]:
        if forward is None or reverse is None:
            return {"status": "healthy", "message": ""}

        forward_state = self.link_endpoint_state(config, peer_node, forward)
        reverse_state = self.link_endpoint_state(config, local_node, reverse)
        if forward_state == "unresolved" and reverse_state == "unresolved":
            return {
                "status": "broken",
                "message": f"Mesh link between {local_node.name} and {peer_node.name} is broken because both sides have no public endpoint.",
            }
        return {"status": "healthy", "message": ""}

    def validate_mesh(self, config: Config, nodes: list[Node], links: list[PeerLink]) -> dict[str, object]:
        errors: list[str] = []
        warnings: list[str] = []
        nodes_by_id = {node.id: node for node in nodes}
        if len(nodes) >= 2 and not links:
            warnings.append("Current config has no peer links.")

        for group_id, group_links in self.peer_link_groups(links).items():
            if not group_links:
                continue
            forward = next((item for item in group_links if item.direction == "forward"), group_links[0])
            reverse = next((item for item in group_links if item.direction == "reverse"), None)
            local_node = nodes_by_id.get(forward.local_node_id)
            peer_node = nodes_by_id.get(forward.peer_node_id)
            if local_node is None or peer_node is None:
                continue
            integrity = self.connection_integrity(config, local_node, peer_node, forward, reverse)
            group_enabled = forward.enabled or (reverse.enabled if reverse else False)
            if group_enabled and str(integrity["status"]) == "broken":
                errors.append(str(integrity["message"]) or f"Mesh link group {group_id} is broken.")

        messages = errors or warnings or ["Topology check passed."]
        return {
            "valid": not errors,
            "messages": messages,
            "errors": errors,
            "warnings": warnings,
        }

    def summarize(self, config: Config, nodes: list[Node], links: list[PeerLink]) -> dict[str, object]:
        nodes_by_id = {node.id: node for node in nodes}
        invalid_node_ids: set[str] = set()
        errors: list[str] = []

        for group_links in self.peer_link_groups(links).values():
            if not group_links:
                continue
            forward = next((item for item in group_links if item.direction == "forward"), group_links[0])
            reverse = next((item for item in group_links if item.direction == "reverse"), None)
            local_node = nodes_by_id.get(forward.local_node_id)
            peer_node = nodes_by_id.get(forward.peer_node_id)
            if local_node is None or peer_node is None:
                continue
            integrity = self.connection_integrity(config, local_node, peer_node, forward, reverse)
            group_enabled = forward.enabled or (reverse.enabled if reverse else False)
            if group_enabled and str(integrity["status"]) == "broken":
                invalid_node_ids.update({local_node.id, peer_node.id})
                errors.append(str(integrity["message"]) or f"Mesh link between {local_node.name} and {peer_node.name} is broken.")

        return {
            "valid": not errors,
            "errors": errors,
            "error_count": len(errors),
            "invalid_node_ids": sorted(invalid_node_ids),
            "invalid_node_count": len(invalid_node_ids),
        }


topology_service = TopologyService()
