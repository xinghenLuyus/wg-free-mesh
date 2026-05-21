# mypy: disable-error-code=attr-defined
from __future__ import annotations

import ipaddress

from app.core.errors import AppError
from app.data.connection import connect
from app.data.repositories.row_mappers import port_forward_rule_from_row
from app.domain.models import Node, PortForwardRule, new_id, now_utc


HOOK_KEYS = ("pre_up", "post_up", "pre_down", "post_down")


class PortForwardRepositoryMixin:
    def list_port_forward_rules(self, config_id: str) -> list[dict[str, object]]:
        self.get_config(config_id)
        nodes_by_id = {node.id: node for node in self.list_nodes(config_id)}
        with connect() as connection:
            rows = connection.execute(
                "SELECT * FROM port_forward_rules WHERE config_id = ? ORDER BY created_at DESC",
                (config_id,),
            ).fetchall()
        return [self._port_forward_payload(port_forward_rule_from_row(row), nodes_by_id) for row in rows]

    def create_port_forward_rule(self, config_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.get_config(config_id)
        from_node = self._port_forward_node(config_id, str(payload.get("from_node_id") or ""), "from")
        to_node = self._port_forward_node(config_id, str(payload.get("to_node_id") or ""), "to")
        if from_node.id == to_node.id:
            raise AppError("PORT_FORWARD_SAME_NODE", "From and To endpoints must be different", 400)
        from_port = self._port_forward_port(payload.get("from_port"), "from_port")
        to_port = self._port_forward_port(payload.get("to_port"), "to_port")
        to_platform = str(payload.get("to_platform") or "").strip()
        if to_platform not in {"linux", "darwin"}:
            raise AppError("PORT_FORWARD_TO_PLATFORM_INVALID", "To endpoint platform must be linux or darwin", 400)
        protocol = str(payload.get("protocol") or "tcp").strip().lower()
        if protocol not in {"tcp", "udp", "all"}:
            raise AppError("PORT_FORWARD_PROTOCOL_INVALID", "Only TCP, UDP and all port forwards are supported", 400)
        self._port_forward_ipv4(from_node, "from")
        self._port_forward_ipv4(to_node, "to")

        now = now_utc().isoformat()
        rule = PortForwardRule(
            id=new_id("pf"),
            config_id=config_id,
            from_node_id=from_node.id,
            from_port=from_port,
            to_node_id=to_node.id,
            to_port=to_port,
            to_platform=to_platform,
            protocol=protocol,
        )
        with connect() as connection:
            existing = connection.execute(
                """
                SELECT id FROM port_forward_rules
                WHERE to_node_id = ? AND to_port = ?
                  AND (protocol = ? OR protocol = 'all' OR ? = 'all')
                LIMIT 1
                """,
                (to_node.id, to_port, protocol, protocol),
            ).fetchone()
            if existing is not None:
                raise AppError("PORT_FORWARD_TO_PORT_IN_USE", "To endpoint port is already managed by another forward", 409)
            connection.execute(
                """
                INSERT INTO port_forward_rules
                  (id, config_id, from_node_id, from_port, to_node_id, to_port, to_platform, protocol, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rule.id, config_id, from_node.id, from_port, to_node.id, to_port, to_platform, protocol, 1, now, now),
            )
        return self._port_forward_payload(rule, {from_node.id: from_node, to_node.id: to_node})

    def update_port_forward_rule_enabled(self, rule_id: str, enabled: bool) -> dict[str, object]:
        now = now_utc().isoformat()
        with connect() as connection:
            row = connection.execute("SELECT * FROM port_forward_rules WHERE id = ?", (rule_id,)).fetchone()
            if row is None:
                raise AppError("PORT_FORWARD_NOT_FOUND", "Port forward rule not found", 404)
            rule = port_forward_rule_from_row(row)
            connection.execute("UPDATE port_forward_rules SET enabled = ?, updated_at = ? WHERE id = ?", (int(enabled), now, rule_id))
        updated = rule.model_copy(update={"enabled": enabled, "updated_at": now_utc()})
        nodes = {
            updated.from_node_id: self.get_node_without_managed_hooks(updated.from_node_id),
            updated.to_node_id: self.get_node_without_managed_hooks(updated.to_node_id),
        }
        return self._port_forward_payload(updated, nodes)

    def delete_port_forward_rule(self, rule_id: str) -> dict[str, str]:
        with connect() as connection:
            row = connection.execute("SELECT * FROM port_forward_rules WHERE id = ?", (rule_id,)).fetchone()
            if row is None:
                raise AppError("PORT_FORWARD_NOT_FOUND", "Port forward rule not found", 404)
            rule = port_forward_rule_from_row(row)
            connection.execute("DELETE FROM port_forward_rules WHERE id = ?", (rule_id,))
        return {"config_id": rule.config_id, "to_node_id": rule.to_node_id}

    def managed_hooks_for_node(self, config_id: str, node: Node) -> dict[str, list[dict[str, str]]]:
        hooks: dict[str, list[dict[str, str]]] = {key: [] for key in HOOK_KEYS}
        if not node.virtual_ip:
            return hooks
        with connect() as connection:
            rows = connection.execute(
                "SELECT * FROM port_forward_rules WHERE config_id = ? AND to_node_id = ? AND enabled = 1 ORDER BY created_at ASC",
                (config_id, node.id),
            ).fetchall()
        nodes_by_id = {item.id: item for item in self.list_nodes_without_managed_hooks(config_id)}
        for row in rows:
            rule = port_forward_rule_from_row(row)
            from_node = nodes_by_id.get(rule.from_node_id)
            if from_node is None or not from_node.virtual_ip:
                continue
            for hook_key, command in self._port_forward_hook_commands(rule, from_node, node).items():
                hooks[hook_key].append(
                    {
                        "source": "port_forward",
                        "source_id": rule.id,
                        "command": command,
                        "label": self._port_forward_label(rule, from_node, node),
                    }
                )
        return hooks

    def managed_hook_commands_for_node(self, config_id: str, node: Node) -> dict[str, list[str]]:
        managed = self.managed_hooks_for_node(config_id, node)
        return {key: [item["command"] for item in managed[key]] for key in HOOK_KEYS}

    def list_nodes_without_managed_hooks(self, config_id: str) -> list[Node]:
        self.get_config(config_id)
        with connect() as connection:
            rows = connection.execute("SELECT * FROM nodes WHERE config_id = ? ORDER BY created_at ASC", (config_id,)).fetchall()
        from app.data.repositories.row_mappers import node_from_row

        return [node_from_row(row) for row in rows]

    def _port_forward_payload(self, rule: PortForwardRule, nodes_by_id: dict[str, Node]) -> dict[str, object]:
        from_node = nodes_by_id[rule.from_node_id]
        to_node = nodes_by_id[rule.to_node_id]
        return {
            **rule.model_dump(mode="json"),
            "from_node": self._port_forward_node_payload(from_node),
            "to_node": self._port_forward_node_payload(to_node),
        }

    def _port_forward_node_payload(self, node: Node) -> dict[str, object]:
        return {"id": node.id, "name": node.name, "virtual_ip": node.virtual_ip, "enabled": node.enabled}

    def _port_forward_node(self, config_id: str, node_id: str, role: str) -> Node:
        node = self.get_node_without_managed_hooks(node_id)
        if node.config_id != config_id or not node.enabled:
            raise AppError("PORT_FORWARD_NODE_INVALID", f"{role.title()} endpoint must be enabled in this config", 400)
        if not node.virtual_ip:
            raise AppError("PORT_FORWARD_VIRTUAL_IP_REQUIRED", f"{role.title()} endpoint needs virtual IP", 400)
        return node

    def get_node_without_managed_hooks(self, node_id: str) -> Node:
        with connect() as connection:
            row = connection.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise AppError("NODE_NOT_FOUND", "Node not found", 404, {"node_id": node_id})
        from app.data.repositories.row_mappers import node_from_row

        return node_from_row(row)

    def _port_forward_port(self, value: object, field: str) -> int:
        try:
            port = int(str(value))
        except (TypeError, ValueError) as exc:
            raise AppError("PORT_FORWARD_PORT_INVALID", f"{field} must be a valid port", 400) from exc
        if port < 1 or port > 65535:
            raise AppError("PORT_FORWARD_PORT_INVALID", f"{field} must be a valid port", 400)
        return port

    def _port_forward_ipv4(self, node: Node, role: str) -> str:
        try:
            interface = ipaddress.ip_interface(str(node.virtual_ip))
        except ValueError as exc:
            raise AppError("PORT_FORWARD_IPV4_REQUIRED", f"{role.title()} endpoint needs IPv4 virtual IP", 400) from exc
        if interface.version != 4:
            raise AppError("PORT_FORWARD_IPV4_REQUIRED", f"{role.title()} endpoint needs IPv4 virtual IP", 400)
        return str(interface.ip)

    def _port_forward_label(self, rule: PortForwardRule, from_node: Node, to_node: Node) -> str:
        return f"From {self._port_forward_ipv4(from_node, 'from')}:{rule.from_port} To {self._port_forward_ipv4(to_node, 'to')}:{rule.to_port}"

    def _port_forward_hook_commands(self, rule: PortForwardRule, from_node: Node, to_node: Node) -> dict[str, str]:
        commands = [self._port_forward_hook_commands_for_protocol(rule, from_node, to_node, protocol) for protocol in self._port_forward_protocols(rule)]
        return {
            "post_up": "; ".join(item["post_up"] for item in commands),
            "pre_down": "; ".join(item["pre_down"] for item in commands),
        }

    def _port_forward_protocols(self, rule: PortForwardRule) -> tuple[str, ...]:
        return ("tcp", "udp") if rule.protocol == "all" else (rule.protocol,)

    def _port_forward_hook_commands_for_protocol(
        self,
        rule: PortForwardRule,
        from_node: Node,
        to_node: Node,
        protocol: str,
    ) -> dict[str, str]:
        from_ip = self._port_forward_ipv4(from_node, "from")
        to_ip = self._port_forward_ipv4(to_node, "to")
        if rule.to_platform == "darwin":
            anchor = f"wfm/{rule.id}/{protocol}"
            add_rule = (
                f"printf 'rdr pass on %i inet proto {protocol} from any to {to_ip} port {rule.to_port} "
                f"-> {from_ip} port {rule.from_port}\\n' | pfctl -a {anchor} -f - && pfctl -E"
            )
            return {"post_up": add_rule, "pre_down": f"pfctl -a {anchor} -F all"}
        comment = f"wfm-{rule.id}-{protocol}"
        dnat = (
            f"iptables -t nat -A PREROUTING -d {to_ip} -p {protocol} --dport {rule.to_port} "
            f"-m comment --comment {comment} -j DNAT --to-destination {from_ip}:{rule.from_port}"
        )
        forward = (
            f"iptables -A FORWARD -p {protocol} -d {from_ip} --dport {rule.from_port} "
            f"-m comment --comment {comment} -j ACCEPT"
        )
        snat = (
            f"iptables -t nat -A POSTROUTING -p {protocol} -d {from_ip} --dport {rule.from_port} "
            f"-m comment --comment {comment} -j MASQUERADE"
        )
        delete = (
            f"iptables -t nat -D PREROUTING -d {to_ip} -p {protocol} --dport {rule.to_port} "
            f"-m comment --comment {comment} -j DNAT --to-destination {from_ip}:{rule.from_port}; "
            f"iptables -D FORWARD -p {protocol} -d {from_ip} --dport {rule.from_port} "
            f"-m comment --comment {comment} -j ACCEPT; "
            f"iptables -t nat -D POSTROUTING -p {protocol} -d {from_ip} --dport {rule.from_port} "
            f"-m comment --comment {comment} -j MASQUERADE"
        )
        return {"post_up": f"{dnat}; {forward}; {snat}", "pre_down": delete}
