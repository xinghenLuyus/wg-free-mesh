from __future__ import annotations

import ipaddress
import json
from pathlib import Path
import re
import shutil
from collections.abc import Iterable
from sqlite3 import Row
from typing import cast

from app.core.errors import AppError
from app.domain.models import (
    Config,
    ConfigSyncState,
    ConnectivityState,
    ControlAction,
    ControlStatus,
    EndpointControlLog,
    EndpointFamily,
    EndpointMode,
    EndpointPortMode,
    EndpointRuntimeStatus,
    Node,
    NodeConfigState,
    NodeType,
    PeerLink,
    WgRuntimeState,
    derive_public_key,
    generate_private_key,
    generate_key_pair,
    new_id,
    now_utc,
    sha256_text,
)
from app.infrastructure.database import connect, data_dir, wireguard_dir
from app.projections.config_list_projection import config_list_projection
from app.projections.config_overview_projection import config_overview_projection
from app.projections.system_status_projection import system_status_projection
from app.repositories.naming import node_config_artifact_stem as _node_config_artifact_stem, validate_config_name
from app.repositories.row_mappers import (
    bool_value as _bool_value,
    config_from_row as _config_from_row,
    endpoint_family_from_row as _endpoint_family_from_row,
    json_list as _json_list,
    log_from_row as _log_from_row,
    node_from_row as _node_from_row,
    parse_datetime as _parse_datetime,
    peer_link_from_row as _peer_link_from_row,
    runtime_from_row as _runtime_from_row,
    state_from_row as _state_from_row,
)
from app.services.topology_service import topology_service


def _int_value(value: object, default: int) -> int:
    if value is None or value == "":
        return default
    return int(str(value))


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(str(value))


def _str_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _is_ipv6_literal(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value.strip("[]")), ipaddress.IPv6Address)
    except ValueError:
        return False


def _endpoint_family_or_none(payload: dict[str, object]) -> str | None:
    if str(payload.get("endpoint_mode", "auto")) != "auto":
        return None
    family = str(payload.get("endpoint_ref_family") or "ipv4")
    return "ipv6" if family == "ipv6" else "ipv4"


def _endpoint_family_value(value: object) -> str:
    return "ipv6" if str(value or "ipv4") == "ipv6" else "ipv4"


def _link_payload(payload: dict[str, object], direction: str, row: Row | None = None) -> dict[str, object]:
    nested = payload.get(direction)
    if isinstance(nested, dict):
        return nested

    local_node_id = payload.get("local_node_id", row["local_node_id"] if row else None)
    peer_node_id = payload.get("peer_node_id", row["peer_node_id"] if row else None)
    if direction == "reverse" and row is None:
        local_node_id = payload.get("peer_node_id")
        peer_node_id = payload.get("local_node_id")

    return {
        "local_node_id": local_node_id,
        "peer_node_id": peer_node_id,
        "allowed_ips": payload.get(
            "allowed_ips_forward" if direction == "forward" else "allowed_ips_reverse",
            row["allowed_ips"] if row else None,
        ),
        "persistent_keepalive": payload.get("persistent_keepalive", row["persistent_keepalive"] if row else None),
        "preshared_key": payload.get("preshared_key", row["preshared_key"] if row else None),
        "endpoint_mode": payload.get("endpoint_mode", row["endpoint_mode"] if row else "auto"),
        "endpoint_ref_family": payload.get("endpoint_ref_family", row["endpoint_ref_family"] if row else "ipv4"),
        "endpoint_manual_host": payload.get("endpoint_manual_host", row["endpoint_manual_host"] if row else None),
        "endpoint_port_mode": payload.get("endpoint_port_mode", row["endpoint_port_mode"] if row else "ref_peer_listen_port"),
        "endpoint_manual_port": payload.get("endpoint_manual_port", row["endpoint_manual_port"] if row else None),
        "enabled": payload.get("enabled", row["enabled"] if row else True),
    }


def _normalize_tags(tags: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        tag = str(item).strip()
        if tag and tag not in normalized:
            normalized.append(tag)
    return sorted(normalized)


def _payload_tags(value: object, default: Iterable[str] = ()) -> list[str]:
    if value is None:
        return _normalize_tags(default)
    if isinstance(value, str):
        return _normalize_tags([value])
    if isinstance(value, Iterable):
        return _normalize_tags(value)
    return _normalize_tags([value])


def _node_type_value(value: object) -> NodeType:
    if isinstance(value, NodeType):
        return value
    return NodeType(str(value))


def _control_action_value(value: object) -> ControlAction:
    if isinstance(value, ControlAction):
        return value
    return ControlAction(str(value))


def normalize_allowed_ips(value: str) -> str:
    tokens = [item.strip() for item in value.split(",") if item.strip()]
    if not tokens:
        raise AppError("INVALID_ALLOWED_IPS", "allowed_ips is required", 400)
    normalized: list[str] = []
    for token in tokens:
        try:
            ipaddress.ip_network(token, strict=False)
        except ValueError as exc:
            raise AppError("INVALID_ALLOWED_IPS", f"Invalid CIDR: {token}", 400) from exc
        if token not in normalized:
            normalized.append(token)
    return ",".join(normalized)


class SQLiteStore:
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
            default_listen_port=_int_value(payload.get("default_listen_port"), 51820),
            default_mtu=_int_or_none(payload.get("default_mtu")),
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
                "default_listen_port": _int_value(payload.get("default_listen_port"), current.default_listen_port),
                "default_mtu": _int_or_none(payload.get("default_mtu")),
                "default_dns": str(payload.get("default_dns") or "") or None,
                "auto_sync": payload.get("auto_sync", current.auto_sync),
                "updated_at": now_utc(),
            }
        )
        validate_config_name(updated.name)
        with connect() as connection:
            existing = connection.execute(
                "SELECT id FROM configs WHERE name = ? AND id != ?",
                (updated.name, config_id),
            ).fetchone()
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
            recalculated_node_ids = {
                node.id for node in nodes_by_id.values() if node.listen_port is None
            }
            for link in self.list_peer_links(config_id):
                peer_node = nodes_by_id.get(link.peer_node_id)
                if (
                    link.endpoint_mode == EndpointMode.auto
                    and peer_node is not None
                    and peer_node.listen_port is None
                ):
                    recalculated_node_ids.add(link.local_node_id)
            if recalculated_node_ids:
                change_hints.append(
                    {
                        "code": "CONFIG_ENDPOINTS_RECALCULATED",
                        "level": "info",
                        "count": len(recalculated_node_ids),
                    }
                )
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
            rows = connection.execute(
                "SELECT * FROM nodes WHERE config_id = ? ORDER BY created_at ASC",
                (config_id,),
            ).fetchall()
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
            listen_port=_int_or_none(payload.get("listen_port")),
            virtual_ip=str(payload.get("virtual_ip") or "") or self.suggest_virtual_ip(config_id),
            mtu=_int_or_none(payload.get("mtu")),
            dns=str(payload.get("dns") or "") or None,
            auto_sync=config.auto_sync if payload.get("auto_sync") is None else bool(payload.get("auto_sync")),
            node_type=_node_type_value(payload.get("node_type", NodeType.dynamic)),
            public_key=public_key,
            private_key=private_key,
            tags=_payload_tags(payload.get("tags")),
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
            for tag in _normalize_tags(node.tags):
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
                "ipv4_address": _str_or_none(payload.get("ipv4_address")) if "ipv4_address" in payload else current.ipv4_address,
                "ipv6_address": _str_or_none(payload.get("ipv6_address")) if "ipv6_address" in payload else current.ipv6_address,
                "listen_port": _int_or_none(payload.get("listen_port")) if "listen_port" in payload else current.listen_port,
                "virtual_ip": _str_or_none(payload.get("virtual_ip")) if "virtual_ip" in payload else current.virtual_ip,
                "mtu": _int_or_none(payload.get("mtu")) if "mtu" in payload else current.mtu,
                "dns": _str_or_none(payload.get("dns")) if "dns" in payload else current.dns,
                "auto_sync": payload.get("auto_sync", current.auto_sync),
                "node_type": _node_type_value(payload.get("node_type", current.node_type)),
                "private_key": str(payload.get("private_key") or current.private_key),
                "public_key": str(payload.get("public_key") or current.public_key),
                "tags": _payload_tags(payload.get("tags"), current.tags),
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
            rows = connection.execute(
                "SELECT name FROM config_tags WHERE config_id = ? ORDER BY name ASC",
                (config_id,),
            ).fetchall()
        names = sorted(set(counts.keys()).union(row["name"] for row in rows))
        return [{"name": name, "count": counts.get(name, 0)} for name in names]

    def create_tag(self, config_id: str, tag: str) -> dict[str, object]:
        self.get_config(config_id)
        normalized = _normalize_tags([tag])
        if not normalized:
            raise AppError("INVALID_TAG", "Tag is required", 400)
        name = normalized[0]
        with connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)",
                (config_id, name, now_utc().isoformat()),
            )
        count = next((item["count"] for item in self.list_tags(config_id) if item["name"] == name), 0)
        return {"name": name, "count": count}

    def replace_node_tags(self, node_id: str, tags: Iterable[object]) -> Node:
        current = self.get_node(node_id)
        updated_tags = _normalize_tags(tags)
        now = now_utc().isoformat()
        with connect() as connection:
            connection.execute(
                "UPDATE nodes SET tags_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(updated_tags, ensure_ascii=True), now, node_id),
            )
            for tag in updated_tags:
                connection.execute(
                    "INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)",
                    (current.config_id, tag, now),
                )
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
            connection.execute(
                "INSERT OR IGNORE INTO config_tags (config_id, name, created_at) VALUES (?, ?, ?)",
                (config_id, normalized_tag, now),
            )
            for node_id in requested_ids:
                node = nodes_by_id[node_id]
                tags = _normalize_tags([*node.tags, normalized_tag])
                connection.execute(
                    "UPDATE nodes SET tags_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(tags, ensure_ascii=True), now, node_id),
                )
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
                tags = _normalize_tags([item for item in node.tags if item != normalized_tag])
                connection.execute(
                    "UPDATE nodes SET tags_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(tags, ensure_ascii=True), now, node.id),
                )
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
            rows = connection.execute(
                "SELECT * FROM peer_links WHERE config_id = ? ORDER BY created_at ASC",
                (config_id,),
            ).fetchall()
        return [_peer_link_from_row(row) for row in rows]

    def _peer_link_groups(self, config_id: str) -> dict[str, list[PeerLink]]:
        return topology_service.peer_link_groups(self.list_peer_links(config_id))

    def _link_endpoint_state(self, config: Config, peer_node: Node, link: PeerLink | None) -> str:
        return topology_service.link_endpoint_state(config, peer_node, link)

    def _connection_integrity(
        self,
        config: Config,
        local_node: Node,
        peer_node: Node,
        forward: PeerLink | None,
        reverse: PeerLink | None,
    ) -> dict[str, object]:
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

        public_endpoint_changed = (
            current.ipv4_address != updated.ipv4_address
            or current.ipv6_address != updated.ipv6_address
            or current.listen_port != updated.listen_port
        )
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
            hints.append(
                {
                    "code": "NODE_ENDPOINTS_RECALCULATED",
                    "level": "info",
                    "count": len(recalculated_endpoint_node_ids),
                    "cleared_keepalive_count": len(keepalive_clear_ids),
                }
            )
        if virtual_ip_changed and related_group_ids:
            hints.append(
                {
                    "code": "VIRTUAL_IP_CHANGED_REVIEW_ALLOWED_IPS",
                    "level": "warning",
                    "count": len(related_group_ids),
                }
            )

        return {
            "affected_node_ids": sorted(affected_node_ids),
            "keepalive_clear_ids": sorted(keepalive_clear_ids),
            "change_hints": hints,
        }

    def build_peer_link_draft(
        self,
        config_id: str,
        node_id: str,
        peer_node_id: str,
        endpoint_ref_family: str = "ipv4",
    ) -> dict[str, object]:
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
        return {
            "node": node.model_dump(mode="json"),
            "connections": connections,
            "validation": self._validate_mesh_payload(config_id),
        }

    def create_peer_link_group(self, config_id: str, payload: dict[str, object]) -> list[PeerLink]:
        config = self.get_config(config_id)
        forward = _link_payload(payload, "forward")
        reverse = _link_payload(payload, "reverse")
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
            {
                "id": new_id("plink"),
                "local_node_id": local_node.id,
                "peer_node_id": peer_node.id,
                "direction": "forward",
                "payload": forward,
            },
            {
                "id": new_id("plink"),
                "local_node_id": peer_node.id,
                "peer_node_id": local_node.id,
                "direction": "reverse",
                "payload": reverse,
            },
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
                        _endpoint_family_or_none(item_payload),
                        str(item_payload.get("endpoint_manual_host") or "") or None,
                        str(item_payload.get("endpoint_port_mode", "ref_peer_listen_port")),
                        _int_or_none(item_payload.get("endpoint_manual_port")),
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
                data = _link_payload(payload, direction, row)
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
                        _endpoint_family_or_none(data),
                        str(data.get("endpoint_manual_host") or "") or None,
                        str(data.get("endpoint_port_mode", row["endpoint_port_mode"])),
                        _int_or_none(data.get("endpoint_manual_port")) if "endpoint_manual_port" in data else row["endpoint_manual_port"],
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

    def get_node_config_state(self, config_id: str, node_id: str) -> NodeConfigState:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM node_config_state WHERE config_id = ? AND node_id = ?",
                (config_id, node_id),
            ).fetchone()
        if row is None:
            raise AppError("NODE_STATE_NOT_FOUND", "Node config state not found", 404)
        return _state_from_row(row)

    def get_runtime(self, config_id: str, node_id: str) -> EndpointRuntimeStatus:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM endpoint_runtime_status WHERE config_id = ? AND node_id = ?",
                (config_id, node_id),
            ).fetchone()
        if row is None:
            raise AppError("RUNTIME_NOT_FOUND", "Node runtime state not found", 404)
        return _runtime_from_row(row)

    def list_runtime_snapshot(self, config_id: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for node in self.list_nodes(config_id):
            runtime = self.get_runtime(config_id, node.id)
            state = self.get_node_config_state(config_id, node.id)
            items.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "node_type": node.node_type,
                    "online": runtime.online,
                    "connectivity_state": runtime.connectivity_state,
                    "wg_running": runtime.wg_running,
                    "wg_runtime_state": runtime.wg_runtime_state,
                    "config_sync_state": runtime.config_sync_state,
                    "server_apply_status": self._sync_status_from_state(state),
                    "peers_online": runtime.peers_online,
                    "peers_total": runtime.peers_total,
                    "last_seen": runtime.last_seen,
                    "last_probe_sent_at": runtime.last_probe_sent_at,
                    "last_probe_ack_at": runtime.last_probe_ack_at,
                }
            )
        return items

    def list_endpoint_logs(self, config_id: str, node_id: str, limit: int = 50) -> list[EndpointControlLog]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM endpoint_control_logs
                WHERE config_id = ? AND node_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (config_id, node_id, limit),
            ).fetchall()
        return [_log_from_row(row) for row in rows]

    def create_control_log(self, config_id: str, node_id: str, action: str, requested_by: str = "admin") -> EndpointControlLog:
        self.get_node(node_id)
        log = EndpointControlLog(
            config_id=config_id,
            node_id=node_id,
            action=_control_action_value(action),
            requested_by=requested_by,
            summary="Command recorded, waiting for server-side simulated execution",
        )
        now = log.created_at.isoformat()
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO endpoint_control_logs
                  (id, request_id, config_id, node_id, action, status, requested_by, summary, detail, requested_at, ack_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.request_id,
                    log.config_id,
                    log.node_id,
                    log.action.value,
                    log.status.value,
                    log.requested_by,
                    log.summary,
                    log.detail,
                    log.requested_at.isoformat(),
                    None,
                    now,
                    now,
                ),
            )
        return log

    def complete_control_log(self, request_id: str, status: ControlStatus, summary: str, detail: str = "") -> EndpointControlLog:
        with connect() as connection:
            row = connection.execute("SELECT * FROM endpoint_control_logs WHERE request_id = ?", (request_id,)).fetchone()
            if row is None:
                raise AppError("CONTROL_LOG_NOT_FOUND", "Control log not found", 404)
            ack_at = now_utc().isoformat()
            connection.execute(
                """
                UPDATE endpoint_control_logs
                SET status = ?, summary = ?, detail = ?, ack_at = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (status.value, summary, detail, ack_at, ack_at, request_id),
            )
        with connect() as connection:
            final_row = connection.execute("SELECT * FROM endpoint_control_logs WHERE request_id = ?", (request_id,)).fetchone()
        return _log_from_row(final_row)

    def apply_control_action(self, config_id: str, node_id: str, action: str) -> dict[str, object]:
        runtime = self.get_runtime(config_id, node_id)
        now = now_utc()
        updates: dict[str, object] = {
            "updated_at": now.isoformat(),
            "last_control_channel_seen_at": now.isoformat(),
            "last_seen": runtime.last_seen.isoformat() if runtime.last_seen else None,
            "last_probe_sent_at": runtime.last_probe_sent_at.isoformat() if runtime.last_probe_sent_at else None,
            "last_probe_ack_at": runtime.last_probe_ack_at.isoformat() if runtime.last_probe_ack_at else None,
            "last_connectivity_reason": runtime.last_connectivity_reason,
            "online": int(runtime.online),
            "wg_running": int(runtime.wg_running),
            "connectivity_state": runtime.connectivity_state.value,
            "wg_runtime_state": runtime.wg_runtime_state.value,
            "config_sync_state": runtime.config_sync_state.value,
        }
        summary = "Control command recorded"
        if action == ControlAction.probe:
            updates["connectivity_state"] = ConnectivityState.online.value if runtime.online else ConnectivityState.offline.value
            updates["last_probe_sent_at"] = now.isoformat()
            updates["last_probe_ack_at"] = now.isoformat()
            updates["last_connectivity_reason"] = "server-simulated-probe"
            summary = "Probe completed with server-side simulated state"
        elif action == ControlAction.start:
            updates["wg_running"] = 1
            updates["wg_runtime_state"] = WgRuntimeState.running.value
            updates["online"] = 1
            updates["connectivity_state"] = ConnectivityState.online.value
            updates["last_seen"] = now.isoformat()
            summary = "WireGuard marked as running"
        elif action == ControlAction.stop:
            updates["wg_running"] = 0
            updates["wg_runtime_state"] = WgRuntimeState.stopped.value
            updates["online"] = 0
            updates["connectivity_state"] = ConnectivityState.offline.value
            updates["last_connectivity_reason"] = "manual-stop"
            summary = "WireGuard marked as stopped"
        elif action == ControlAction.restart:
            updates["wg_running"] = 1
            updates["wg_runtime_state"] = WgRuntimeState.running.value
            updates["online"] = 1
            updates["connectivity_state"] = ConnectivityState.online.value
            updates["last_seen"] = now.isoformat()
            summary = "WireGuard marked as restarted"
        elif action == ControlAction.sync:
            self.sync_node(config_id, node_id, requested_by="endpoint-control")
            updates["config_sync_state"] = ConfigSyncState.in_sync.value
            summary = "Node config synced to staged state"
        elif action == ControlAction.wg_show:
            summary = "wg_show request recorded, deferred to client phase"
        else:
            raise AppError("INVALID_ACTION", "Unsupported control action", 400)
        with connect() as connection:
            connection.execute(
                """
                UPDATE endpoint_runtime_status
                SET online = ?, connectivity_state = ?, wg_running = ?, wg_runtime_state = ?, config_sync_state = ?,
                    last_seen = ?, last_probe_sent_at = ?, last_probe_ack_at = ?, last_control_channel_seen_at = ?,
                    last_connectivity_reason = ?, updated_at = ?
                WHERE config_id = ? AND node_id = ?
                """,
                (
                    updates["online"],
                    updates["connectivity_state"],
                    updates["wg_running"],
                    updates["wg_runtime_state"],
                    updates["config_sync_state"],
                    updates["last_seen"],
                    updates["last_probe_sent_at"],
                    updates["last_probe_ack_at"],
                    updates["last_control_channel_seen_at"],
                    updates["last_connectivity_reason"],
                    updates["updated_at"],
                    config_id,
                    node_id,
                ),
            )
        return {"summary": summary, "runtime": self.get_runtime(config_id, node_id)}

    def get_node_endpoint_status(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        runtime = self.get_runtime(config_id, node_id)
        state = self.get_node_config_state(config_id, node_id)
        logs = self.list_endpoint_logs(config_id, node_id, limit=1)
        return {
            "node": node,
            "runtime": runtime,
            "config_state": {
                "desired_version": state.desired_version,
                "staged_version": state.staged_version,
                "confirmed_version": state.confirmed_version,
                "desired_sha256": state.desired_sha256,
                "staged_sha256": state.staged_sha256,
                "confirmed_sha256": state.confirmed_sha256,
                "reported_local_sha256": state.reported_local_sha256,
                "reported_local_version": state.reported_local_version,
                "status": runtime.config_sync_state,
                "server_apply_status": self._sync_status_from_state(state),
            },
            "last_control": logs[0] if logs else None,
        }

    def build_wg_preview(self, config_id: str, node_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        node = self.get_node(node_id)
        links = [item for item in self.list_peer_links(config_id) if item.local_node_id == node_id and item.enabled]
        lines = ["[Interface]", f"PrivateKey = {node.private_key}"]
        if node.virtual_ip:
            lines.append(f"Address = {node.virtual_ip}")
        lines.append(f"ListenPort = {node.listen_port or config.default_listen_port}")
        effective_dns = node.dns or config.default_dns
        if effective_dns:
            lines.append(f"DNS = {effective_dns}")
        effective_mtu = node.mtu or config.default_mtu
        if effective_mtu:
            lines.append(f"MTU = {effective_mtu}")
        for link in links:
            peer_node = self.get_node(link.peer_node_id)
            lines.extend(["", f"# Peer: {peer_node.name}", "[Peer]", f"PublicKey = {peer_node.public_key}", f"AllowedIPs = {link.allowed_ips}"])
            if link.preshared_key:
                lines.append(f"PresharedKey = {link.preshared_key}")
            endpoint = self._resolve_endpoint(config, peer_node, link)
            if endpoint:
                lines.append(f"Endpoint = {endpoint}")
            if endpoint and link.persistent_keepalive:
                lines.append(f"PersistentKeepalive = {link.persistent_keepalive}")
        content = "\n".join(lines) + "\n"
        return {"node_id": node_id, "node_name": node.name, "content": content, "sha256": sha256_text(content)}

    def refresh_config_state(self, config_id: str) -> None:
        config = self.get_config(config_id)
        peer_links = self.list_peer_links(config_id)
        nodes = self.list_nodes(config_id)
        mesh_validation = self._validate_mesh_payload(config_id)
        topology_valid = bool(mesh_validation["valid"])
        for node in nodes:
            preview = self.build_wg_preview(config_id, node.id)
            with connect() as connection:
                row = connection.execute("SELECT * FROM node_config_state WHERE node_id = ?", (node.id,)).fetchone()
                state = _state_from_row(row)
                desired_text = str(preview["content"])
                desired_sha = str(preview["sha256"])
                desired_version = state.desired_version + 1 if state.desired_sha256 != desired_sha else state.desired_version
                staged_text = state.staged_text
                staged_sha = state.staged_sha256
                staged_version = state.staged_version
                now = now_utc().isoformat()
                if node.auto_sync and topology_valid:
                    staged_text = desired_text
                    staged_sha = desired_sha
                    staged_version = desired_version
                connection.execute(
                    """
                    UPDATE node_config_state
                    SET desired_text = ?, desired_sha256 = ?, desired_version = ?, desired_generated_at = ?,
                        staged_text = ?, staged_sha256 = ?, staged_version = ?, staged_updated_at = ?, updated_at = ?
                    WHERE node_id = ?
                    """,
                    (
                        desired_text,
                        desired_sha,
                        desired_version,
                        now,
                        staged_text,
                        staged_sha,
                        staged_version,
                        now if node.auto_sync and topology_valid else state.staged_updated_at.isoformat() if state.staged_updated_at else None,
                        now,
                        node.id,
                    ),
                )
                peer_total = len([item for item in peer_links if item.local_node_id == node.id and item.enabled])
                peer_online = 0
                for link in peer_links:
                    if link.local_node_id != node.id or not link.enabled:
                        continue
                    if self.get_runtime(config_id, link.peer_node_id).online:
                        peer_online += 1
                connection.execute(
                    """
                    UPDATE endpoint_runtime_status
                    SET peers_total = ?, peers_online = ?, config_sync_state = ?, updated_at = ?
                    WHERE node_id = ?
                    """,
                    (
                        peer_total,
                        peer_online,
                        ConfigSyncState.in_sync.value if staged_sha == desired_sha and desired_sha else ConfigSyncState.pending.value,
                        now,
                        node.id,
                    ),
                )
                self._write_service_conf(config_id, node.id, staged_text)

    def get_sync_status_for_config(self, config_id: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for node in self.list_nodes(config_id):
            result.append(self.get_sync_status_for_node(config_id, node.id))
        return result

    def get_sync_status_for_node(self, config_id: str, node_id: str) -> dict[str, object]:
        self.get_config(config_id)
        node = self.get_node(node_id)
        state = self.get_node_config_state(config_id, node_id)
        runtime = self.get_runtime(config_id, node_id)
        mesh_validation = self._validate_mesh_payload(config_id)
        return {
            "node_id": node.id,
            "node_name": node.name,
            "node_type": node.node_type,
            "auto_sync": node.auto_sync,
            "desired_version": state.desired_version,
            "staged_version": state.staged_version,
            "confirmed_version": state.confirmed_version,
            "desired_sha256": state.desired_sha256,
            "staged_sha256": state.staged_sha256,
            "confirmed_sha256": state.confirmed_sha256,
            "reported_local_sha256": state.reported_local_sha256,
            "reported_local_version": state.reported_local_version,
            "status": self._sync_status_from_state(state),
            "runtime_status": runtime.config_sync_state,
            "topology_valid": bool(mesh_validation["valid"]),
            "topology_messages": cast(list[str], mesh_validation["errors"] if not mesh_validation["valid"] else mesh_validation["warnings"]),
        }

    def read_applied_conf(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        state = self.get_node_config_state(config_id, node_id)
        conf_path = self._conf_path(config_id, node_id)
        content = conf_path.read_text(encoding="utf-8") if conf_path.exists() else state.staged_text or ""
        return {
            "exists": bool(content),
            "content": content,
            "node_name": node.name,
            "node_type": node.node_type,
            "source": "server_applied",
            "desired_version": state.desired_version,
            "staged_version": state.staged_version,
        }

    def download_package(self, config_id: str, node_id: str) -> dict[str, object]:
        node = self.get_node(node_id)
        config = self.get_config(config_id)
        applied = self.read_applied_conf(config_id, node_id)
        file_stem = _node_config_artifact_stem(config.name, node.name)
        return {
            "config_id": config_id,
            "node_id": node_id,
            "config_name": config.name,
            "node_name": node.name,
            "filename": f"{file_stem}.conf",
            "content": applied["content"],
            "download_path": f"/api/v1/configs/{config_id}/nodes/{node_id}/download-conf",
        }

    def save_applied_conf(self, config_id: str, node_id: str, content: str) -> dict[str, object]:
        self.get_node(node_id)
        state = self.get_node_config_state(config_id, node_id)
        sha = sha256_text(content)
        version = max(state.staged_version, state.desired_version) + 1
        now = now_utc().isoformat()
        self._write_service_conf(config_id, node_id, content)
        with connect() as connection:
            connection.execute(
                "UPDATE node_config_state SET staged_text = ?, staged_sha256 = ?, staged_version = ?, staged_updated_at = ?, updated_at = ? WHERE node_id = ?",
                (content, sha, version, now, now, node_id),
            )
            connection.execute(
                "UPDATE endpoint_runtime_status SET config_sync_state = ?, updated_at = ? WHERE node_id = ?",
                (ConfigSyncState.in_sync.value, now, node_id),
            )
        return self.get_sync_status_for_node(config_id, node_id)

    def sync_node(self, config_id: str, node_id: str, requested_by: str = "manual") -> dict[str, object]:
        del requested_by
        mesh_validation = self._validate_mesh_payload(config_id)
        if not mesh_validation["valid"]:
            raise AppError("TOPOLOGY_INVALID", "Please resolve topology validation before syncing.", 409, {"messages": mesh_validation["errors"]})
        preview = self.build_wg_preview(config_id, node_id)
        result = self.save_applied_conf(config_id, node_id, str(preview["content"]))
        state = self.get_node_config_state(config_id, node_id)
        return {"message": "Node config synced", "staged_version": state.staged_version, "staged_sha256": state.staged_sha256, "sync_status": result}

    def sync_all(self, config_id: str) -> dict[str, object]:
        mesh_validation = self._validate_mesh_payload(config_id)
        if not mesh_validation["valid"]:
            raise AppError("TOPOLOGY_INVALID", "Please resolve topology validation before syncing.", 409, {"messages": mesh_validation["errors"]})
        synced: list[str] = []
        for node in self.list_nodes(config_id):
            self.sync_node(config_id, node.id, requested_by="sync-all")
            synced.append(node.id)
        return {"message": "All node configs synced", "synced_count": len(synced), "failed_count": 0, "synced": synced, "failed": []}

    def read_setting_json(self, key: str, default: dict[str, object]) -> dict[str, object]:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            parsed = json.loads(row["value"])
        except json.JSONDecodeError:
            return default
        return {**default, **parsed}

    def write_setting_json(self, key: str, value: dict[str, object]) -> None:
        now = now_utc().isoformat()
        with connect() as connection:
            exists = connection.execute("SELECT key FROM system_settings WHERE key = ?", (key,)).fetchone()
            if exists is None:
                connection.execute("INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)", (key, json.dumps(value, ensure_ascii=False), now))
            else:
                connection.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (json.dumps(value, ensure_ascii=False), now, key))

    def read_setting(self, key: str) -> str | None:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def write_setting(self, key: str, value: str) -> None:
        now = now_utc().isoformat()
        with connect() as connection:
            exists = connection.execute("SELECT key FROM system_settings WHERE key = ?", (key,)).fetchone()
            if exists is None:
                connection.execute(
                    "INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, now),
                )
            else:
                connection.execute(
                    "UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?",
                    (value, now, key),
                )

    def delete_setting(self, key: str) -> None:
        with connect() as connection:
            connection.execute("DELETE FROM system_settings WHERE key = ?", (key,))

    def read_password(self) -> str:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = 'auth_password_hash'").fetchone()
        return row["value"] if row else "admin123"

    def update_password(self, current_password: str, new_password: str) -> None:
        if self.read_password() != current_password:
            raise AppError("AUTH_FAILED", "Current password is incorrect", 401)
        with connect() as connection:
            connection.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'auth_password_hash'", (new_password, now_utc().isoformat()))

    def create_keys(self) -> dict[str, str]:
        private_key, public_key = generate_key_pair()
        return {"private_key": private_key, "public_key": public_key}

    def create_preshared_key(self) -> dict[str, str]:
        return {"preshared_key": generate_private_key()}

    def derive_public_key_from_private(self, private_key: str) -> dict[str, str]:
        return {"private_key": private_key, "public_key": derive_public_key(private_key)}

    def system_status(self) -> dict[str, object]:
        configs = self.list_configs()
        nodes = [node for config in configs for node in self.list_nodes(config.id)]
        runtimes = [self.get_runtime(node.config_id, node.id).model_dump(mode="json") for node in nodes]
        return system_status_projection.project(configs, nodes, runtimes, self._topology_issue_summary)

    def config_overview(self, config_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        runtimes = self.list_runtime_snapshot(config_id)
        topology = self._topology_issue_summary(config_id)
        return config_overview_projection.project(
            config=config,
            nodes=nodes,
            runtimes=runtimes,
            peer_link_count=len(self.list_peer_links(config_id)) // 2,
            sync_status=self.get_sync_status_for_config(config_id),
            topology=topology,
        )

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
        endpoint = f"[{host}]:{port}" if _is_ipv6_literal(host) else f"{host}:{port}"
        return f"Auto uses {endpoint}"

    def _peer_link_endpoint_summary(self, config: Config, peer_node: Node, link: PeerLink) -> str:
        if link.endpoint_mode == EndpointMode.none:
            return "No Endpoint"
        if link.endpoint_mode == EndpointMode.manual:
            host = link.endpoint_manual_host or ""
            port = link.endpoint_manual_port
            if not host or not port:
                return "Manual mode requires Host and Port"
            endpoint = f"[{host}]:{port}" if _is_ipv6_literal(host) else f"{host}:{port}"
            return f"Manual uses {endpoint}"
        family = "ipv6" if link.endpoint_ref_family == EndpointFamily.ipv6 else "ipv4"
        return self._endpoint_preview_text(config, peer_node, family)

    def _draft_endpoint_summary(self, config: Config, peer_node: Node, endpoint_mode: str, family: str, manual_host: str | None, manual_port: int | None) -> str:
        if endpoint_mode == EndpointMode.none.value:
            return "No Endpoint"
        if endpoint_mode == EndpointMode.manual.value:
            if not manual_host or not manual_port:
                return "Manual mode requires Host and Port"
            endpoint = f"[{manual_host}]:{manual_port}" if _is_ipv6_literal(manual_host) else f"{manual_host}:{manual_port}"
            return f"Manual uses {endpoint}"
        return self._endpoint_preview_text(config, peer_node, family)

    def _payload_has_endpoint(
        self,
        config: Config,
        peer_node: Node,
        payload: dict[str, object],
    ) -> bool:
        endpoint_mode = str(payload.get("endpoint_mode", EndpointMode.auto.value))
        if endpoint_mode == EndpointMode.none.value:
            return False
        if endpoint_mode == EndpointMode.manual.value:
            return bool(_str_or_none(payload.get("endpoint_manual_host")) and _int_or_none(payload.get("endpoint_manual_port")))

        family = _endpoint_family_value(payload.get("endpoint_ref_family"))
        port = peer_node.listen_port or config.default_listen_port
        return bool(self._endpoint_host_for_family(peer_node, family) and port)

    def _effective_keepalive(
        self,
        config: Config,
        peer_node: Node,
        payload: dict[str, object],
    ) -> int | None:
        if not self._payload_has_endpoint(config, peer_node, payload):
            return None
        return _int_or_none(payload.get("persistent_keepalive"))

    def _keepalive_display(self, keepalive: int | None, has_endpoint: bool) -> str:
        if not has_endpoint:
            return "/"
        if keepalive is None:
            return "Unset"
        return str(keepalive)

    def _peer_link_direction_card(
        self,
        config: Config,
        local_node: Node,
        peer_node: Node,
        link: PeerLink | None,
    ) -> dict[str, object]:
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

    def _validate_link_endpoint_settings(
        self,
        payload: dict[str, object],
    ) -> None:
        endpoint_mode = EndpointMode(str(payload.get("endpoint_mode", EndpointMode.auto)))
        if endpoint_mode == EndpointMode.none:
            return
        if endpoint_mode == EndpointMode.manual:
            if not _str_or_none(payload.get("endpoint_manual_host")) or not _int_or_none(payload.get("endpoint_manual_port")):
                raise AppError("INVALID_ENDPOINT", "Manual Endpoint requires Host and Port.", 400)
            return

    def _validate_mesh_payload(self, config_id: str) -> dict[str, object]:
        return topology_service.validate_mesh(
            self.get_config(config_id),
            self.list_nodes(config_id),
            self.list_peer_links(config_id),
        )

    def _topology_issue_summary(self, config_id: str) -> dict[str, object]:
        return topology_service.summarize(
            self.get_config(config_id),
            self.list_nodes(config_id),
            self.list_peer_links(config_id),
        )

    def _resolve_endpoint(self, config: Config, peer_node: Node, link: PeerLink) -> str | None:
        return topology_service.resolve_endpoint(config, peer_node, link)

    def _conf_path(self, config_id: str, node_id: str) -> Path:
        target = wireguard_dir() / config_id
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{node_id}.conf"

    def _write_service_conf(self, config_id: str, node_id: str, content: str) -> None:
        self._conf_path(config_id, node_id).write_text(content, encoding="utf-8")


store = SQLiteStore()
