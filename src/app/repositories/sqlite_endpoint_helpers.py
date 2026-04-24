# mypy: disable-error-code=attr-defined
from __future__ import annotations

from pathlib import Path

from app.core.errors import AppError
from app.domain.models import Config, EndpointFamily, EndpointMode, EndpointPortMode, Node, NodeConfigState, PeerLink
from app.infrastructure.database import wireguard_dir
from app.repositories.sqlite_common import endpoint_family_value, int_or_none, is_ipv6_literal, str_or_none
from app.services.topology_service import topology_service


class SQLiteEndpointHelpersMixin:
    def _sync_status_from_state(self, state: NodeConfigState) -> str:
        if not state.desired_sha256:
            return "empty"
        if state.staged_sha256 == state.desired_sha256:
            return "in_sync"
        if state.staged_sha256:
            return "staged_outdated"
        return "pending"

    def _endpoint_host_for_family(self, node: Node, family: object) -> str | None:
        family_value = str(family or "ipv4")
        if family_value == "ipv6":
            return node.ipv6_address
        return node.ipv4_address

    def _endpoint_preview_text(self, config: Config, peer_node: Node, family: str) -> str:
        host = self._endpoint_host_for_family(peer_node, family)
        if not host:
            return f"{peer_node.name} has no public {family.upper()} entry; auto mode leaves it empty"
        port = peer_node.listen_port or config.default_listen_port
        endpoint = f"[{host}]:{port}" if is_ipv6_literal(host) else f"{host}:{port}"
        return f"Auto uses {endpoint}"

    def _peer_link_endpoint_summary(self, config: Config, peer_node: Node, link: PeerLink) -> str:
        if link.endpoint_mode == EndpointMode.none:
            return "No Endpoint"
        if link.endpoint_mode == EndpointMode.manual:
            host = link.endpoint_manual_host or ""
            port = link.endpoint_manual_port
            if not host or not port:
                return "Manual mode requires Host and Port"
            endpoint = f"[{host}]:{port}" if is_ipv6_literal(host) else f"{host}:{port}"
            return f"Manual uses {endpoint}"
        family = "ipv6" if link.endpoint_ref_family == EndpointFamily.ipv6 else "ipv4"
        return self._endpoint_preview_text(config, peer_node, family)

    def _draft_endpoint_summary(
        self,
        config: Config,
        peer_node: Node,
        endpoint_mode: str,
        family: str,
        manual_host: str | None,
        manual_port: int | None,
    ) -> str:
        if endpoint_mode == EndpointMode.none.value:
            return "No Endpoint"
        if endpoint_mode == EndpointMode.manual.value:
            if not manual_host or not manual_port:
                return "Manual mode requires Host and Port"
            endpoint = f"[{manual_host}]:{manual_port}" if is_ipv6_literal(manual_host) else f"{manual_host}:{manual_port}"
            return f"Manual uses {endpoint}"
        return self._endpoint_preview_text(config, peer_node, family)

    def _payload_has_endpoint(self, config: Config, peer_node: Node, payload: dict[str, object]) -> bool:
        endpoint_mode = str(payload.get("endpoint_mode", EndpointMode.auto.value))
        if endpoint_mode == EndpointMode.none.value:
            return False
        if endpoint_mode == EndpointMode.manual.value:
            return bool(str_or_none(payload.get("endpoint_manual_host")) and int_or_none(payload.get("endpoint_manual_port")))
        family = endpoint_family_value(payload.get("endpoint_ref_family"))
        port = peer_node.listen_port or config.default_listen_port
        return bool(self._endpoint_host_for_family(peer_node, family) and port)

    def _effective_keepalive(self, config: Config, peer_node: Node, payload: dict[str, object]) -> int | None:
        if not self._payload_has_endpoint(config, peer_node, payload):
            return None
        return int_or_none(payload.get("persistent_keepalive"))

    def _keepalive_display(self, keepalive: int | None, has_endpoint: bool) -> str:
        if not has_endpoint:
            return "/"
        if keepalive is None:
            return "Unset"
        return str(keepalive)

    def _peer_link_direction_card(self, config: Config, local_node: Node, peer_node: Node, link: PeerLink | None) -> dict[str, object]:
        if link is None:
            return {
                "link_id": "",
                "local_node_id": local_node.id,
                "peer_node_id": peer_node.id,
                "allowed_ips": "",
                "persistent_keepalive": None,
                "endpoint_mode": EndpointMode.none.value,
                "endpoint_ref_family": None,
                "endpoint_manual_host": None,
                "endpoint_port_mode": EndpointPortMode.ref_peer_listen_port.value,
                "endpoint_manual_port": None,
                "endpoint_summary": "Missing reverse link",
                "keepalive_display": "/",
            }
        has_endpoint = self._resolve_endpoint(config, peer_node, link) is not None
        return {
            "link_id": link.id,
            "local_node_id": link.local_node_id,
            "peer_node_id": link.peer_node_id,
            "allowed_ips": link.allowed_ips,
            "persistent_keepalive": link.persistent_keepalive,
            "endpoint_mode": link.endpoint_mode,
            "endpoint_ref_family": link.endpoint_ref_family,
            "endpoint_manual_host": link.endpoint_manual_host,
            "endpoint_port_mode": link.endpoint_port_mode,
            "endpoint_manual_port": link.endpoint_manual_port,
            "endpoint_summary": self._peer_link_endpoint_summary(config, peer_node, link),
            "keepalive_display": self._keepalive_display(link.persistent_keepalive, has_endpoint),
        }

    def _peer_link_direction_draft(
        self,
        config: Config,
        local_node: Node,
        peer_node: Node,
        family: str,
        persistent_keepalive: int | None,
    ) -> dict[str, object]:
        has_endpoint = bool(self._endpoint_host_for_family(peer_node, family) and (peer_node.listen_port or config.default_listen_port))
        effective_keepalive = persistent_keepalive if has_endpoint else None
        return {
            "local_node_id": local_node.id,
            "peer_node_id": peer_node.id,
            "allowed_ips": peer_node.virtual_ip or "",
            "persistent_keepalive": effective_keepalive,
            "endpoint_mode": EndpointMode.auto.value,
            "endpoint_ref_family": family,
            "endpoint_manual_host": "",
            "endpoint_port_mode": EndpointPortMode.ref_peer_listen_port.value,
            "endpoint_manual_port": None,
            "endpoint_summary": self._endpoint_preview_text(config, peer_node, family),
            "keepalive_display": self._keepalive_display(effective_keepalive, has_endpoint),
        }

    def _validate_endpoint_references(self, config_id: str, current: Node, updated: Node) -> dict[str, object]:
        return self._reconcile_node_dependency_changes(config_id, current, updated)

    def _validate_link_endpoint_settings(self, payload: dict[str, object]) -> None:
        endpoint_mode = EndpointMode(str(payload.get("endpoint_mode", EndpointMode.auto)))
        if endpoint_mode == EndpointMode.none:
            return
        if endpoint_mode == EndpointMode.manual and (not str_or_none(payload.get("endpoint_manual_host")) or not int_or_none(payload.get("endpoint_manual_port"))):
            raise AppError("INVALID_ENDPOINT", "Manual Endpoint requires Host and Port.", 400)

    def _validate_mesh_payload(self, config_id: str) -> dict[str, object]:
        return topology_service.validate_mesh(self.get_config(config_id), self.list_nodes(config_id), self.list_peer_links(config_id))

    def _topology_issue_summary(self, config_id: str) -> dict[str, object]:
        return topology_service.summarize(self.get_config(config_id), self.list_nodes(config_id), self.list_peer_links(config_id))

    def _resolve_endpoint(self, config: Config, peer_node: Node, link: PeerLink) -> str | None:
        return topology_service.resolve_endpoint(config, peer_node, link)

    def _conf_path(self, config_id: str, node_id: str) -> Path:
        target = wireguard_dir() / config_id
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{node_id}.conf"

    def _write_service_conf(self, config_id: str, node_id: str, content: str) -> None:
        self._conf_path(config_id, node_id).write_text(content, encoding="utf-8")

    def _write_service_conf_if_changed(self, config_id: str, node_id: str, content: str) -> None:
        conf_path = self._conf_path(config_id, node_id)
        if conf_path.exists() and conf_path.read_text(encoding="utf-8") == content:
            return
        conf_path.write_text(content, encoding="utf-8")
