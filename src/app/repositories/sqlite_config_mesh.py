# mypy: disable-error-code=attr-defined
from __future__ import annotations

import ipaddress
import json
import shutil
from collections.abc import Sequence
from typing import cast

from app.core.errors import AppError
from app.domain.models import (
    Config,
    ConfigSyncState,
    ConnectivityState,
    EndpointMode,
    EndpointPortMode,
    Node,
    NodeType,
    PeerLink,
    WgRuntimeState,
    derive_public_key,
    generate_key_pair,
    new_id,
    now_utc,
)
from app.infrastructure.database import connect, wireguard_dir
from app.projections.config_list_projection import config_list_projection
from app.repositories.naming import validate_config_name
from app.repositories.row_mappers import (
    bool_value as _bool_value,
    config_from_row as _config_from_row,
    node_from_row as _node_from_row,
    peer_link_from_row as _peer_link_from_row,
)
from app.repositories.sqlite_common import (
    endpoint_family_or_none,
    int_or_none,
    int_value,
    link_payload,
    node_type_value,
    normalize_allowed_ips,
    normalize_tags,
    payload_tags,
    str_or_none,
)
from app.services.topology_service import topology_service


class SQLiteConfigMeshMixin:
    def list_configs(self) -> list[Config]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  configs.*,
                  COUNT(nodes.id) AS node_count,
                  SUM(CASE WHEN nodes.node_type = 'dynamic' THEN 1 ELSE 0 END) AS dynamic_node_count
                FROM configs
                LEFT JOIN nodes ON nodes.config_id = configs.id
                GROUP BY configs.id
                ORDER BY configs.created_at DESC
                """
            ).fetchall()
        configs = [_config_from_row(row) for row in rows]
        return config_list_projection.project(configs, self._topology_issue_summary)

    def get_config(self, config_id: str) -> Config:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT
                  configs.*,
                  COUNT(nodes.id) AS node_count,
                  SUM(CASE WHEN nodes.node_type = 'dynamic' THEN 1 ELSE 0 END) AS dynamic_node_count
                FROM configs
                LEFT JOIN nodes ON nodes.config_id = configs.id
                WHERE configs.id = ?
                GROUP BY configs.id
                """,
                (config_id,),
            ).fetchone()
        if row is None:
            raise AppError("CONFIG_NOT_FOUND", "Config not found", 404, {"config_id": config_id})
        return _config_from_row(row)

    def create_config(self, payload: dict[str, object]) -> Config:
        name = str(payload["name"]).strip()
        validate_config_name(name)
        now = now_utc().isoformat()
        config = Config(
            name=name,
            description=str(payload.get("description", "") or ""),
            enabled=bool(payload.get("enabled", True)),
            virtual_subnet=str(payload.get("virtual_subnet", "10.66.0.0/24")),
            default_listen_port=int_value(payload.get("default_listen_port"), 51820),
            default_mtu=int_or_none(payload.get("default_mtu")),
            default_dns=str(payload.get("default_dns") or "") or None,
            auto_sync=bool(payload.get("auto_sync", True)),
        )
        with connect() as connection:
            existing = connection.execute("SELECT id FROM configs WHERE name = ?", (config.name,)).fetchone()
            if existing is not None:
                raise AppError("CONFIG_NAME_EXISTS", f"Config {config.name} already exists", 409)
            connection.execute(
                """
                INSERT INTO configs
                  (id, name, description, enabled, virtual_subnet, default_listen_port, default_mtu, default_dns, auto_sync, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.id,
                    config.name,
                    config.description,
                    int(config.enabled),
                    config.virtual_subnet,
                    config.default_listen_port,
                    config.default_mtu,
                    config.default_dns,
                    int(config.auto_sync),
                    now,
                    now,
                ),
            )
        return self.get_config(config.id)

    def update_config(self, config_id: str, payload: dict[str, object]) -> dict[str, object]:
        current = self.get_config(config_id)
        updated = current.model_copy(
            update={
                "name": str(payload.get("name", current.name)).strip(),
                "description": str(payload.get("description", current.description) or ""),
                "enabled": payload.get("enabled", current.enabled),
                "virtual_subnet": str(payload.get("virtual_subnet", current.virtual_subnet)),
                "default_listen_port": int_value(payload.get("default_listen_port"), current.default_listen_port),
                "default_mtu": int_or_none(payload.get("default_mtu")),
                "default_dns": str(payload.get("default_dns") or "") or None,
                "auto_sync": payload.get("auto_sync", current.auto_sync),
                "updated_at": now_utc(),
            }
        )
        validate_config_name(updated.name)
        with connect() as connection:
            existing = connection.execute("SELECT id FROM configs WHERE name = ? AND id != ?", (updated.name, config_id)).fetchone()
            if existing is not None:
                raise AppError("CONFIG_NAME_EXISTS", f"Config {updated.name} already exists", 409)
            connection.execute(
                """
                UPDATE configs
                SET name = ?, description = ?, enabled = ?, virtual_subnet = ?, default_listen_port = ?,
                    default_mtu = ?, default_dns = ?, auto_sync = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.name,
                    updated.description,
                    int(updated.enabled),
                    updated.virtual_subnet,
                    updated.default_listen_port,
                    updated.default_mtu,
                    updated.default_dns,
                    int(updated.auto_sync),
                    updated.updated_at.isoformat(),
                    config_id,
                ),
            )
        node_ids = [node.id for node in self.list_nodes(config_id)]
        affected_node_ids: set[str] = set(node_ids)
        change_hints: list[dict[str, object]] = []

        if current.default_listen_port != updated.default_listen_port:
            nodes_by_id = {node.id: node for node in self.list_nodes(config_id)}
            recalculated_node_ids = {node.id for node in nodes_by_id.values() if node.listen_port is None}
            for link in self.list_peer_links(config_id):
                peer_node = nodes_by_id.get(link.peer_node_id)
                if link.endpoint_mode == EndpointMode.auto and peer_node is not None and peer_node.listen_port is None:
                    recalculated_node_ids.add(link.local_node_id)
            if recalculated_node_ids:
                change_hints.append({"code": "CONFIG_ENDPOINTS_RECALCULATED", "level": "info", "count": len(recalculated_node_ids)})
                affected_node_ids.update(recalculated_node_ids)

        self.refresh_config_state(config_id)
        config = self.get_config(config_id)
        return {
            **config.model_dump(mode="json"),
            "change_hints": change_hints,
            "affected_node_ids": sorted(affected_node_ids),
        }

    def delete_config(self, config_id: str) -> None:
        self.get_config(config_id)
        with connect() as connection:
            connection.execute("DELETE FROM configs WHERE id = ?", (config_id,))
        target = wireguard_dir() / config_id
        if target.exists():
            shutil.rmtree(target)

    def list_nodes(self, config_id: str) -> list[Node]:
        self.get_config(config_id)
        with connect() as connection:
            rows = connection.execute("SELECT * FROM nodes WHERE config_id = ? ORDER BY created_at ASC", (config_id,)).fetchall()
        return [_node_from_row(row) for row in rows]

    def get_node(self, node_id: str) -> Node:
        with connect() as connection:
            row = connection.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise AppError("NODE_NOT_FOUND", "Node not found", 404, {"node_id": node_id})
        return _node_from_row(row)

    def suggest_virtual_ip(self, config_id: str) -> str:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        try:
            network = ipaddress.ip_network(config.virtual_subnet, strict=False)
        except ValueError as exc:
            raise AppError("INVALID_SUBNET", "Config virtual_subnet is invalid", 400) from exc
        used: set[object] = set()
        for node in nodes:
            if not node.virtual_ip:
                continue
            try:
                iface = ipaddress.ip_interface(node.virtual_ip)
            except ValueError:
                continue
            if iface.ip in network:
                used.add(iface.ip)
        for host in network.hosts():
            if host not in used:
                prefix = 32 if getattr(host, "version", 4) == 4 else 128
                return f"{host}/{prefix}"
        raise AppError("IP_POOL_EXHAUSTED", "No available address in the virtual subnet", 400)

    def validate_virtual_ip(self, config_id: str, value: str, exclude_node_id: str | None = None) -> dict[str, object]:
        if not value.strip():
            return {"valid": False, "warning": "Virtual IP is required"}
        try:
            iface = ipaddress.ip_interface(value)
        except ValueError:
            return {"valid": False, "warning": "IP format is invalid"}
        for node in self.list_nodes(config_id):
            if node.id == exclude_node_id:
                continue
            if node.virtual_ip == value:
                return {"valid": False, "warning": f"{value} is already used by node {node.name}"}
            if node.virtual_ip:
                try:
                    existing = ipaddress.ip_interface(node.virtual_ip)
                except ValueError:
                    continue
                if existing.ip == iface.ip:
                    return {"valid": False, "warning": f"{iface.ip} is already used by node {node.name}"}
        return {"valid": True, "warning": ""}

    def create_node(self, config_id: str, payload: dict[str, object]) -> Node:
        config = self.get_config(config_id)
        private_key, generated_public = generate_key_pair()
        private_key = str(payload.get("private_key") or "").strip() or private_key
        public_key = str(payload.get("public_key") or "").strip() or derive_public_key(private_key) or generated_public
        node_name = str(payload["name"]).strip()
        if not node_name:
            raise AppError("INVALID_NODE_NAME", "Name is required", 400)
        node = Node(
            config_id=config_id,
            name=node_name,
            ipv4_address=str(payload.get("ipv4_address") or "") or None,
            ipv6_address=str(payload.get("ipv6_address") or "") or None,
            listen_port=int_or_none(payload.get("listen_port")),
            virtual_ip=str(payload.get("virtual_ip") or "") or self.suggest_virtual_ip(config_id),
            mtu=int_or_none(payload.get("mtu")),
            dns=str(payload.get("dns") or "") or None,
            auto_sync=config.auto_sync if payload.get("auto_sync") is None else bool(payload.get("auto_sync")),
            node_type=node_type_value(payload.get("node_type", NodeType.dynamic)),
            public_key=public_key,
            private_key=private_key,
            tags=payload_tags(payload.get("tags")),
        )
        validation = self.validate_virtual_ip(config_id, node.virtual_ip or "")
        if not validation["valid"]:
            raise AppError("INVALID_VIRTUAL_IP", str(validation["warning"]), 400)
        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO nodes
                  (id, config_id, name, ipv4_address, ipv6_address, listen_port, virtual_ip, mtu, dns, auto_sync, node_type, public_key, private_key, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    config_id,
                    node.name,
                    node.ipv4_address,
                    node.ipv6_address,
                    node.listen_port,
                    node.virtual_ip,
                    node.mtu,
                    node.dns,
                    int(node.auto_sync),
                    node.node_type.value,
                    node.public_key,
                    node.private_key,
                    json.dumps(node.tags, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            connection.execute("UPDATE configs SET updated_at = ? WHERE id = ?", (now, config_id))
            connection.execute(
                "INSERT INTO node_config_state (id, config_id, node_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (new_id("ncs"), config_id, node.id, now, now),
            )
            for tag in normalize_tags(node.tags):
                connection.execute(
                    "INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)",
                    (config_id, tag, now),
                )
            connection.execute(
                """
                INSERT INTO endpoint_runtime_status
                  (id, config_id, node_id, online, connectivity_state, wg_running, wg_runtime_state, config_sync_state, peers_online, peers_total, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("rt"),
                    config_id,
                    node.id,
                    0,
                    ConnectivityState.offline,
                    0,
                    WgRuntimeState.stopped,
                    ConfigSyncState.pending,
                    0,
                    0,
                    now,
                    now,
                ),
            )
        self.refresh_config_state(config_id)
        return self.get_node(node.id)

    def update_node(self, node_id: str, payload: dict[str, object]) -> dict[str, object]:
        current = self.get_node(node_id)
        updated = current.model_copy(
            update={
                "name": str(payload.get("name", current.name)).strip(),
                "ipv4_address": str_or_none(payload.get("ipv4_address")) if "ipv4_address" in payload else current.ipv4_address,
                "ipv6_address": str_or_none(payload.get("ipv6_address")) if "ipv6_address" in payload else current.ipv6_address,
                "listen_port": int_or_none(payload.get("listen_port")) if "listen_port" in payload else current.listen_port,
                "virtual_ip": str_or_none(payload.get("virtual_ip")) if "virtual_ip" in payload else current.virtual_ip,
                "mtu": int_or_none(payload.get("mtu")) if "mtu" in payload else current.mtu,
                "dns": str_or_none(payload.get("dns")) if "dns" in payload else current.dns,
                "auto_sync": payload.get("auto_sync", current.auto_sync),
                "node_type": node_type_value(payload.get("node_type", current.node_type)),
                "private_key": str(payload.get("private_key") or current.private_key),
                "public_key": str(payload.get("public_key") or current.public_key),
                "tags": payload_tags(payload.get("tags"), current.tags),
                "updated_at": now_utc(),
            }
        )
        if not updated.name:
            raise AppError("INVALID_NODE_NAME", "Name is required", 400)
        if payload.get("private_key") and not payload.get("public_key"):
            updated = updated.model_copy(update={"public_key": derive_public_key(updated.private_key)})
        validation = self.validate_virtual_ip(current.config_id, updated.virtual_ip or "", exclude_node_id=node_id)
        if not validation["valid"]:
            raise AppError("INVALID_VIRTUAL_IP", str(validation["warning"]), 400)
        dependency_changes = self._validate_endpoint_references(current.config_id, current, updated)
        with connect() as connection:
            connection.execute(
                """
                UPDATE nodes
                SET name = ?, ipv4_address = ?, ipv6_address = ?, listen_port = ?, virtual_ip = ?, mtu = ?, dns = ?,
                    auto_sync = ?, node_type = ?, public_key = ?, private_key = ?, tags_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.name,
                    updated.ipv4_address,
                    updated.ipv6_address,
                    updated.listen_port,
                    updated.virtual_ip,
                    updated.mtu,
                    updated.dns,
                    int(updated.auto_sync),
                    updated.node_type.value,
                    updated.public_key,
                    updated.private_key,
                    json.dumps(updated.tags, ensure_ascii=True),
                    updated.updated_at.isoformat(),
                    node_id,
                ),
            )
            keepalive_clear_ids = cast(list[str], dependency_changes["keepalive_clear_ids"])
            if keepalive_clear_ids:
                placeholders = ",".join("?" for _ in keepalive_clear_ids)
                connection.execute(
                    f"UPDATE peer_links SET persistent_keepalive = NULL, updated_at = ? WHERE id IN ({placeholders})",
                    (updated.updated_at.isoformat(), *keepalive_clear_ids),
                )
        self.refresh_config_state(current.config_id)
        node = self.get_node(node_id)
        return {
            **node.model_dump(mode="json"),
            "change_hints": dependency_changes["change_hints"],
            "affected_node_ids": dependency_changes["affected_node_ids"],
        }

    def list_tags(self, config_id: str) -> list[dict[str, object]]:
        self.get_config(config_id)
        counts: dict[str, int] = {}
        for node in self.list_nodes(config_id):
            for tag in node.tags:
                counts[tag] = counts.get(tag, 0) + 1
        with connect() as connection:
            rows = connection.execute("SELECT name FROM config_tags WHERE config_id = ? ORDER BY name ASC", (config_id,)).fetchall()
        names = sorted(set(counts.keys()).union(row["name"] for row in rows))
        return [{"name": name, "count": counts.get(name, 0)} for name in names]

    def create_tag(self, config_id: str, tag: str) -> dict[str, object]:
        self.get_config(config_id)
        normalized = normalize_tags([tag])
        if not normalized:
            raise AppError("INVALID_TAG", "Tag is required", 400)
        name = normalized[0]
        with connect() as connection:
            connection.execute("INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)", (config_id, name, now_utc().isoformat()))
        count = next((item["count"] for item in self.list_tags(config_id) if item["name"] == name), 0)
        return {"name": name, "count": count}

    def replace_node_tags(self, node_id: str, tags: Sequence[object]) -> Node:
        current = self.get_node(node_id)
        updated_tags = normalize_tags(tags)
        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute("UPDATE nodes SET tags_json = ?, updated_at = ? WHERE id = ?", (json.dumps(updated_tags, ensure_ascii=True), now, node_id))
            for tag in updated_tags:
                connection.execute("INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)", (current.config_id, tag, now))
        self.refresh_config_state(current.config_id)
        return self.get_node(node_id)

    def apply_tag_to_nodes(self, config_id: str, tag: str, node_ids: list[str]) -> list[Node]:
        normalized_tag = str(tag).strip()
        if not normalized_tag:
            raise AppError("INVALID_TAG", "Tag is required", 400)
        requested_ids = list(dict.fromkeys(str(node_id) for node_id in node_ids if str(node_id).strip()))
        if not requested_ids:
            return []
        nodes_by_id = {node.id: node for node in self.list_nodes(config_id)}
        missing_ids = [node_id for node_id in requested_ids if node_id not in nodes_by_id]
        if missing_ids:
            raise AppError("NODE_CONFIG_MISMATCH", "Endpoint does not belong to this config", 400, {"node_ids": missing_ids})

        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute("INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)", (config_id, normalized_tag, now))
            for node_id in requested_ids:
                node = nodes_by_id[node_id]
                tags = normalize_tags([*node.tags, normalized_tag])
                connection.execute("UPDATE nodes SET tags_json = ?, updated_at = ? WHERE id = ?", (json.dumps(tags, ensure_ascii=True), now, node_id))
        self.refresh_config_state(config_id)
        return [self.get_node(node_id) for node_id in requested_ids]

    def remove_tag_from_node(self, node_id: str, tag: str) -> Node:
        current = self.get_node(node_id)
        normalized_tag = str(tag).strip()
        return self.replace_node_tags(node_id, [item for item in current.tags if item != normalized_tag])

    def delete_tag_from_config(self, config_id: str, tag: str) -> int:
        normalized_tag = str(tag).strip()
        if not normalized_tag:
            raise AppError("INVALID_TAG", "Tag is required", 400)
        nodes = self.list_nodes(config_id)
        affected = [node for node in nodes if normalized_tag in node.tags]
        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute("DELETE FROM config_tags WHERE config_id = ? AND name = ?", (config_id, normalized_tag))
            for node in affected:
                tags = normalize_tags([item for item in node.tags if item != normalized_tag])
                connection.execute("UPDATE nodes SET tags_json = ?, updated_at = ? WHERE id = ?", (json.dumps(tags, ensure_ascii=True), now, node.id))
        if affected:
            self.refresh_config_state(config_id)
        return len(affected)

    def delete_node(self, node_id: str) -> None:
        node = self.get_node(node_id)
        with connect() as connection:
            connection.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.refresh_config_state(node.config_id)

    def list_peer_links(self, config_id: str) -> list[PeerLink]:
        self.get_config(config_id)
        with connect() as connection:
            rows = connection.execute("SELECT * FROM peer_links WHERE config_id = ? ORDER BY created_at ASC", (config_id,)).fetchall()
        return [_peer_link_from_row(row) for row in rows]

    def _peer_link_groups(self, config_id: str) -> dict[str, list[PeerLink]]:
        return topology_service.peer_link_groups(self.list_peer_links(config_id))

    def _link_endpoint_state(self, config: Config, peer_node: Node, link: PeerLink | None) -> str:
        return topology_service.link_endpoint_state(config, peer_node, link)

    def _connection_integrity(self, config: Config, local_node: Node, peer_node: Node, forward: PeerLink | None, reverse: PeerLink | None) -> dict[str, object]:
        return topology_service.connection_integrity(config, local_node, peer_node, forward, reverse)

    def _reconcile_node_dependency_changes(self, config_id: str, current: Node, updated: Node) -> dict[str, object]:
        links = self.list_peer_links(config_id)
        nodes_by_id = {node.id: node for node in self.list_nodes(config_id)}
        nodes_by_id[current.id] = updated
        config = self.get_config(config_id)

        affected_node_ids: set[str] = {current.id}
        keepalive_clear_ids: set[str] = set()
        related_group_ids: set[str] = set()
        recalculated_endpoint_node_ids: set[str] = set()
        hints: list[dict[str, object]] = []

        public_endpoint_changed = current.ipv4_address != updated.ipv4_address or current.ipv6_address != updated.ipv6_address or current.listen_port != updated.listen_port
        virtual_ip_changed = current.virtual_ip != updated.virtual_ip

        for link in links:
            if current.id not in {link.local_node_id, link.peer_node_id}:
                continue
            affected_node_ids.add(link.local_node_id)
            affected_node_ids.add(link.peer_node_id)
            related_group_ids.add(link.link_group_id)
            if public_endpoint_changed and link.peer_node_id == current.id and link.endpoint_mode == EndpointMode.auto:
                recalculated_endpoint_node_ids.add(link.local_node_id)
                if link.persistent_keepalive is not None and self._resolve_endpoint(config, updated, link) is None:
                    keepalive_clear_ids.add(link.id)

        if public_endpoint_changed and recalculated_endpoint_node_ids:
            hints.append({"code": "NODE_ENDPOINTS_RECALCULATED", "level": "info", "count": len(recalculated_endpoint_node_ids), "cleared_keepalive_count": len(keepalive_clear_ids)})
        if virtual_ip_changed and related_group_ids:
            hints.append({"code": "VIRTUAL_IP_CHANGED_REVIEW_ALLOWED_IPS", "level": "warning", "count": len(related_group_ids)})

        return {"affected_node_ids": sorted(affected_node_ids), "keepalive_clear_ids": sorted(keepalive_clear_ids), "change_hints": hints}

    def build_peer_link_draft(self, config_id: str, node_id: str, peer_node_id: str, endpoint_ref_family: str = "ipv4") -> dict[str, object]:
        config = self.get_config(config_id)
        local_node = self.get_node(node_id)
        peer_node = self.get_node(peer_node_id)
        if local_node.config_id != config_id or peer_node.config_id != config_id:
            raise AppError("NODE_CONFIG_MISMATCH", "Link node does not belong to this config", 400)
        if local_node.id == peer_node.id:
            raise AppError("INVALID_PEER_LINK", "A node cannot link to itself", 400)

        family = "ipv6" if endpoint_ref_family == "ipv6" else "ipv4"
        warnings: list[str] = []
        if not peer_node.virtual_ip:
            warnings.append(f"{peer_node.name} is missing virtual IP. Forward AllowedIPs must be filled manually.")
        if not local_node.virtual_ip:
            warnings.append(f"{local_node.name} is missing virtual IP. Reverse AllowedIPs must be filled manually.")
        if not self._endpoint_host_for_family(peer_node, family):
            warnings.append(f"{peer_node.name} has no public {family.upper()} entry. Forward auto Endpoint will be empty.")
        if not self._endpoint_host_for_family(local_node, family):
            warnings.append(f"{local_node.name} has no public {family.upper()} entry. Reverse auto Endpoint will be empty.")

        return {
            "local_node": local_node.model_dump(mode="json"),
            "peer_node": peer_node.model_dump(mode="json"),
            "endpoint_ref_family": family,
            "forward": self._peer_link_direction_draft(config, local_node, peer_node, family, 25),
            "reverse": self._peer_link_direction_draft(config, peer_node, local_node, family, 25),
            "warnings": warnings,
        }

    def mesh_workspace(self, config_id: str, node_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        node = self.get_node(node_id)
        if node.config_id != config_id:
            raise AppError("NODE_CONFIG_MISMATCH", "Node does not belong to this config", 400)

        links = self.list_peer_links(config_id)
        nodes_by_id = {item.id: item for item in self.list_nodes(config_id)}
        reverse_by_group: dict[str, PeerLink] = {}
        for link in links:
            if link.peer_node_id == node_id:
                reverse_by_group[link.link_group_id] = link

        connections: list[dict[str, object]] = []
        for link in links:
            if link.local_node_id != node_id:
                continue
            reverse = reverse_by_group.get(link.link_group_id)
            peer_node = nodes_by_id[link.peer_node_id]
            integrity = self._connection_integrity(config, node, peer_node, link, reverse)
            connections.append(
                {
                    "link_group_id": link.link_group_id,
                    "peer_node": peer_node.model_dump(mode="json"),
                    "enabled": link.enabled,
                    "has_preshared_key": bool(link.preshared_key or reverse and reverse.preshared_key),
                    "preshared_key": link.preshared_key or reverse.preshared_key if reverse else link.preshared_key,
                    "notes": link.notes or reverse.notes if reverse else link.notes,
                    "updated_at": max(link.updated_at, reverse.updated_at if reverse else link.updated_at).isoformat(),
                    "forward": self._peer_link_direction_card(config, node, peer_node, link),
                    "reverse": self._peer_link_direction_card(config, peer_node, node, reverse) if reverse else None,
                    "integrity_status": integrity["status"],
                    "integrity_message": integrity["message"],
                }
            )
        return {"node": node.model_dump(mode="json"), "connections": connections, "validation": self._validate_mesh_payload(config_id)}

    def create_peer_link_group(self, config_id: str, payload: dict[str, object]) -> list[PeerLink]:
        config = self.get_config(config_id)
        forward = link_payload(payload, "forward")
        reverse = link_payload(payload, "reverse")
        local_node = self.get_node(str(forward["local_node_id"]))
        peer_node = self.get_node(str(forward["peer_node_id"]))
        if local_node.config_id != config_id or peer_node.config_id != config_id:
            raise AppError("NODE_CONFIG_MISMATCH", "Link node does not belong to this config", 400)
        if str(reverse["local_node_id"]) != peer_node.id or str(reverse["peer_node_id"]) != local_node.id:
            raise AppError("INVALID_PEER_LINK", "Bidirectional link node direction mismatch", 400)
        self._validate_link_endpoint_settings(forward)
        self._validate_link_endpoint_settings(reverse)
        group_id = new_id("group")
        now = now_utc().isoformat()
        rows = [
            {"id": new_id("plink"), "local_node_id": local_node.id, "peer_node_id": peer_node.id, "direction": "forward", "payload": forward},
            {"id": new_id("plink"), "local_node_id": peer_node.id, "peer_node_id": local_node.id, "direction": "reverse", "payload": reverse},
        ]
        with connect() as connection:
            for item in rows:
                item_payload = cast(dict[str, object], item["payload"])
                item_peer_node = peer_node if item["direction"] == "forward" else local_node
                connection.execute(
                    """
                    INSERT INTO peer_links
                      (id, config_id, local_node_id, peer_node_id, link_group_id, direction, enabled, allowed_ips,
                       persistent_keepalive, preshared_key, endpoint_mode, endpoint_ref_family, endpoint_manual_host,
                       endpoint_port_mode, endpoint_manual_port, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        config_id,
                        item["local_node_id"],
                        item["peer_node_id"],
                        group_id,
                        item["direction"],
                        int(bool(payload.get("enabled", item_payload.get("enabled", True)))),
                        normalize_allowed_ips(str(item_payload["allowed_ips"])),
                        self._effective_keepalive(config, item_peer_node, item_payload),
                        str(payload.get("preshared_key") or item_payload.get("preshared_key") or "") or None,
                        str(item_payload.get("endpoint_mode", "auto")),
                        endpoint_family_or_none(item_payload),
                        str(item_payload.get("endpoint_manual_host") or "") or None,
                        str(item_payload.get("endpoint_port_mode", "ref_peer_listen_port")),
                        int_or_none(item_payload.get("endpoint_manual_port")),
                        str(payload.get("notes", "")),
                        now,
                        now,
                    ),
                )
        self.refresh_config_state(config_id)
        return [item for item in self.list_peer_links(config_id) if item.link_group_id == group_id]

    def update_peer_link_group(self, group_id: str, payload: dict[str, object]) -> list[PeerLink]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM peer_links WHERE link_group_id = ?", (group_id,)).fetchall()
            if not rows:
                raise AppError("PEER_LINK_NOT_FOUND", "Peer link group not found", 404)
            config_id = rows[0]["config_id"]
            config = self.get_config(config_id)
            for row in rows:
                direction = str(row["direction"])
                data = link_payload(payload, direction, row)
                self._validate_link_endpoint_settings(data)
                peer_node = self.get_node(str(data.get("peer_node_id", row["peer_node_id"])))
                connection.execute(
                    """
                    UPDATE peer_links
                    SET enabled = ?, allowed_ips = ?, persistent_keepalive = ?, preshared_key = ?, endpoint_mode = ?,
                        endpoint_ref_family = ?, endpoint_manual_host = ?, endpoint_port_mode = ?, endpoint_manual_port = ?,
                        notes = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        int(bool(payload.get("enabled", _bool_value(row["enabled"])))),
                        normalize_allowed_ips(str(data.get("allowed_ips", row["allowed_ips"]))),
                        self._effective_keepalive(config, peer_node, data),
                        str(payload.get("preshared_key") or data.get("preshared_key") or row["preshared_key"] or "") or None,
                        str(data.get("endpoint_mode", row["endpoint_mode"])),
                        endpoint_family_or_none(data),
                        str(data.get("endpoint_manual_host") or "") or None,
                        str(data.get("endpoint_port_mode", row["endpoint_port_mode"])),
                        int_or_none(data.get("endpoint_manual_port")) if "endpoint_manual_port" in data else row["endpoint_manual_port"],
                        str(payload.get("notes", row["notes"])),
                        now_utc().isoformat(),
                        row["id"],
                    ),
                )
        self.refresh_config_state(config_id)
        return [item for item in self.list_peer_links(config_id) if item.link_group_id == group_id]

    def delete_peer_link_group(self, group_id: str) -> None:
        with connect() as connection:
            row = connection.execute("SELECT config_id FROM peer_links WHERE link_group_id = ? LIMIT 1", (group_id,)).fetchone()
            if row is None:
                raise AppError("PEER_LINK_NOT_FOUND", "Peer link group not found", 404)
            config_id = row["config_id"]
            connection.execute("DELETE FROM peer_links WHERE link_group_id = ?", (group_id,))
        self.refresh_config_state(config_id)
