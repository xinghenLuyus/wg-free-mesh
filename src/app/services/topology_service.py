from __future__ import annotations

import ipaddress
from typing import TypedDict

from app.domain.models import Config, EndpointMode, EndpointPortMode, Node, PeerLink


def _is_ipv6_literal(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value.strip("[]")), ipaddress.IPv6Address)
    except ValueError:
        return False


class TopologyService:
    class DuplicateEnabledGroupError(TypedDict):
        message: str
        node_ids: set[str]

    def peer_link_groups(self, links: list[PeerLink]) -> dict[str, list[PeerLink]]:
        groups: dict[str, list[PeerLink]] = {}
        for link in links:
            groups.setdefault(link.link_group_id, []).append(link)
        return groups

    def _pair_key(self, left_node_id: str, right_node_id: str) -> tuple[str, str]:
        if left_node_id <= right_node_id:
            return left_node_id, right_node_id
        return right_node_id, left_node_id

    def _group_primary_nodes(self, group_links: list[PeerLink]) -> tuple[str, str] | None:
        if not group_links:
            return None
        primary = next((item for item in group_links if item.direction == "forward"), group_links[0])
        return primary.local_node_id, primary.peer_node_id

    def _invalid_enabled_link_references(
        self,
        enabled_links: list[PeerLink],
        nodes_by_id: dict[str, Node],
    ) -> tuple[set[str], set[str]]:
        invalid_reference_ids: set[str] = set()
        affected_active_node_ids: set[str] = set()
        for link in enabled_links:
            for node_id, counterpart_id in (
                (link.local_node_id, link.peer_node_id),
                (link.peer_node_id, link.local_node_id),
            ):
                node = nodes_by_id.get(node_id)
                if node is not None and node.enabled:
                    continue
                invalid_reference_ids.add(node_id)
                counterpart = nodes_by_id.get(counterpart_id)
                if counterpart is not None and counterpart.enabled:
                    affected_active_node_ids.add(counterpart_id)
        return invalid_reference_ids, affected_active_node_ids

    def duplicate_enabled_group_errors(self, nodes: list[Node], links: list[PeerLink]) -> list[DuplicateEnabledGroupError]:
        nodes_by_id = {node.id: node for node in nodes}
        enabled_groups_by_pair: dict[tuple[str, str], list[str]] = {}

        for group_id, group_links in self.peer_link_groups(links).items():
            if not any(link.enabled for link in group_links):
                continue
            primary_nodes = self._group_primary_nodes(group_links)
            if primary_nodes is None:
                continue
            left_node = nodes_by_id.get(primary_nodes[0])
            right_node = nodes_by_id.get(primary_nodes[1])
            if left_node is None or right_node is None or not left_node.enabled or not right_node.enabled:
                continue
            pair_key = self._pair_key(*primary_nodes)
            enabled_groups_by_pair.setdefault(pair_key, []).append(group_id)

        duplicate_errors: list[TopologyService.DuplicateEnabledGroupError] = []
        for (left_node_id, right_node_id), group_ids in enabled_groups_by_pair.items():
            if len(group_ids) < 2:
                continue
            left_node = nodes_by_id.get(left_node_id)
            right_node = nodes_by_id.get(right_node_id)
            left_name = left_node.name if left_node else left_node_id
            right_name = right_node.name if right_node else right_node_id
            duplicate_errors.append(
                {
                    "message": (
                        f"Duplicate enabled peer links found between {left_name} and {right_name}. "
                        "Only one enabled link group is allowed for the same node pair."
                    ),
                    "node_ids": {left_node_id, right_node_id},
                }
            )
        return duplicate_errors

    def duplicate_enabled_group_messages_by_group(self, nodes: list[Node], links: list[PeerLink]) -> dict[str, str]:
        grouped_links = self.peer_link_groups(links)
        nodes_by_id = {node.id: node for node in nodes}
        enabled_groups_by_pair: dict[tuple[str, str], list[str]] = {}

        for group_id, group_links in grouped_links.items():
            if not any(link.enabled for link in group_links):
                continue
            primary_nodes = self._group_primary_nodes(group_links)
            if primary_nodes is None:
                continue
            left_node = nodes_by_id.get(primary_nodes[0])
            right_node = nodes_by_id.get(primary_nodes[1])
            if left_node is None or right_node is None or not left_node.enabled or not right_node.enabled:
                continue
            pair_key = self._pair_key(*primary_nodes)
            enabled_groups_by_pair.setdefault(pair_key, []).append(group_id)

        messages_by_group: dict[str, str] = {}
        for (left_node_id, right_node_id), group_ids in enabled_groups_by_pair.items():
            if len(group_ids) < 2:
                continue
            left_node = nodes_by_id.get(left_node_id)
            right_node = nodes_by_id.get(right_node_id)
            left_name = left_node.name if left_node else left_node_id
            right_name = right_node.name if right_node else right_node_id
            message = (
                f"Duplicate enabled peer links found between {left_name} and {right_name}. "
                "Only one enabled link group is allowed for the same node pair."
            )
            for group_id in group_ids:
                messages_by_group[group_id] = message
        return messages_by_group

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
        group_enabled = bool((forward and forward.enabled) or (reverse and reverse.enabled))
        if group_enabled and local_node.enabled and not peer_node.enabled:
            return {
                "status": "broken",
                "message": f"Mesh link from {local_node.name} references disabled endpoint {peer_node.name}.",
            }
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
        active_nodes = [node for node in nodes if node.enabled]
        if len(active_nodes) >= 2 and not [link for link in links if link.enabled]:
            warnings.append("Current config has no peer links.")

        for duplicate in self.duplicate_enabled_group_errors(nodes, links):
            errors.append(str(duplicate["message"]))

        for group_id, group_links in self.peer_link_groups(links).items():
            if not group_links:
                continue
            enabled_links = [link for link in group_links if link.enabled]
            missing_or_disabled_ids, _affected_active_node_ids = self._invalid_enabled_link_references(
                enabled_links,
                nodes_by_id,
            )
            if missing_or_disabled_ids:
                errors.append(
                    f"Enabled Mesh link group {group_id} references missing or disabled endpoint: "
                    f"{', '.join(sorted(missing_or_disabled_ids))}."
                )
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

        for duplicate in self.duplicate_enabled_group_errors(nodes, links):
            errors.append(str(duplicate["message"]))
            invalid_node_ids.update(set(duplicate["node_ids"]))

        for group_links in self.peer_link_groups(links).values():
            if not group_links:
                continue
            enabled_links = [link for link in group_links if link.enabled]
            missing_or_disabled_ids, affected_active_node_ids = self._invalid_enabled_link_references(
                enabled_links,
                nodes_by_id,
            )
            if missing_or_disabled_ids:
                invalid_node_ids.update(affected_active_node_ids)
                errors.append(
                    f"Enabled Mesh link group {group_links[0].link_group_id} references missing or disabled endpoint: "
                    f"{', '.join(sorted(missing_or_disabled_ids))}."
                )
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
