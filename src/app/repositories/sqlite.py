from __future__ import annotations

import ipaddress
import json
import re
import shutil
from collections.abc import Iterable
from pathlib import Path
from sqlite3 import Row
from typing import cast
from zipfile import ZIP_DEFLATED, ZipFile

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
    SnapshotInfo,
    WgRuntimeState,
    derive_public_key,
    generate_private_key,
    generate_key_pair,
    new_id,
    now_utc,
    sha256_text,
)
from app.infrastructure.database import backups_dir, connect, data_dir, wireguard_dir
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
    snapshot_from_row as _snapshot_from_row,
    state_from_row as _state_from_row,
)


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
        raise AppError("INVALID_ALLOWED_IPS", "allowed_ips 不能为空", 400)
    normalized: list[str] = []
    for token in tokens:
        try:
            ipaddress.ip_network(token, strict=False)
        except ValueError as exc:
            raise AppError("INVALID_ALLOWED_IPS", f"无效的 CIDR: {token}", 400) from exc
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
        return [_config_from_row(row) for row in rows]

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
            raise AppError("CONFIG_NOT_FOUND", "配置不存在", 404, {"config_id": config_id})
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
                raise AppError("CONFIG_NAME_EXISTS", f"配置 {config.name} 已存在", 409)
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

    def update_config(self, config_id: str, payload: dict[str, object]) -> Config:
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
                raise AppError("CONFIG_NAME_EXISTS", f"配置 {updated.name} 已存在", 409)
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
        self.refresh_config_state(config_id)
        return self.get_config(config_id)

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
            raise AppError("NODE_NOT_FOUND", "节点不存在", 404, {"node_id": node_id})
        return _node_from_row(row)

    def suggest_virtual_ip(self, config_id: str) -> str:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        try:
            network = ipaddress.ip_network(config.virtual_subnet, strict=False)
        except ValueError as exc:
            raise AppError("INVALID_SUBNET", "配置的 virtual_subnet 不合法", 400) from exc
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
        raise AppError("IP_POOL_EXHAUSTED", "虚拟子网没有可用地址", 400)

    def validate_virtual_ip(self, config_id: str, value: str, exclude_node_id: str | None = None) -> dict[str, object]:
        config = self.get_config(config_id)
        if not value.strip():
            return {"valid": False, "warning": "虚拟 IP 不能为空"}
        try:
            network = ipaddress.ip_network(config.virtual_subnet, strict=False)
            iface = ipaddress.ip_interface(value)
        except ValueError:
            return {"valid": False, "warning": "IP 格式非法"}
        if iface.ip not in network:
            return {"valid": False, "warning": f"{value} 不在子网 {config.virtual_subnet} 内"}
        for node in self.list_nodes(config_id):
            if node.id == exclude_node_id:
                continue
            if node.virtual_ip == value:
                return {"valid": False, "warning": f"{value} 已被节点 {node.name} 使用"}
        return {"valid": True, "warning": ""}

    def create_node(self, config_id: str, payload: dict[str, object]) -> Node:
        self.get_config(config_id)
        private_key, generated_public = generate_key_pair()
        private_key = str(payload.get("private_key") or "").strip() or private_key
        public_key = str(payload.get("public_key") or "").strip() or derive_public_key(private_key) or generated_public
        node_name = str(payload["name"]).strip()
        if not node_name:
            raise AppError("INVALID_NODE_NAME", "名称不能为空", 400)
        node = Node(
            config_id=config_id,
            name=node_name,
            ipv4_address=str(payload.get("ipv4_address") or "") or None,
            ipv6_address=str(payload.get("ipv6_address") or "") or None,
            listen_port=_int_or_none(payload.get("listen_port")),
            virtual_ip=str(payload.get("virtual_ip") or "") or self.suggest_virtual_ip(config_id),
            mtu=_int_or_none(payload.get("mtu")),
            dns=str(payload.get("dns") or "") or None,
            auto_sync=bool(payload.get("auto_sync", True)),
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

    def update_node(self, node_id: str, payload: dict[str, object]) -> Node:
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
            raise AppError("INVALID_NODE_NAME", "名称不能为空", 400)
        if payload.get("private_key") and not payload.get("public_key"):
            updated = updated.model_copy(update={"public_key": derive_public_key(updated.private_key)})
        validation = self.validate_virtual_ip(current.config_id, updated.virtual_ip or "", exclude_node_id=node_id)
        if not validation["valid"]:
            raise AppError("INVALID_VIRTUAL_IP", str(validation["warning"]), 400)
        self._validate_endpoint_references(current.config_id, current, updated)
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
        self.refresh_config_state(current.config_id)
        return self.get_node(node_id)

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
            raise AppError("INVALID_TAG", "标签不能为空", 400)
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
            raise AppError("INVALID_TAG", "标签不能为空", 400)

        requested_ids = list(dict.fromkeys(str(node_id) for node_id in node_ids if str(node_id).strip()))
        if not requested_ids:
            return []

        nodes_by_id = {node.id: node for node in self.list_nodes(config_id)}
        missing_ids = [node_id for node_id in requested_ids if node_id not in nodes_by_id]
        if missing_ids:
            raise AppError("NODE_CONFIG_MISMATCH", "端点不属于当前配置", 400, {"node_ids": missing_ids})

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
            raise AppError("INVALID_TAG", "标签不能为空", 400)

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
            raise AppError("NODE_CONFIG_MISMATCH", "链路节点不属于当前配置", 400)
        if local_node.id == peer_node.id:
            raise AppError("INVALID_PEER_LINK", "不能连接到自身节点", 400)

        family = "ipv6" if endpoint_ref_family == "ipv6" else "ipv4"
        warnings: list[str] = []
        if not peer_node.virtual_ip:
            warnings.append(f"{peer_node.name} 缺少虚拟 IP，主向 AllowedIPs 需要手动填写。")
        if not local_node.virtual_ip:
            warnings.append(f"{local_node.name} 缺少虚拟 IP，反向 AllowedIPs 需要手动填写。")
        if not self._endpoint_host_for_family(peer_node, family):
            warnings.append(f"{peer_node.name} 没有公网 {family.upper()} 入口，主向自动 Endpoint 会留空。")
        if not self._endpoint_host_for_family(local_node, family):
            warnings.append(f"{local_node.name} 没有公网 {family.upper()} 入口，反向自动 Endpoint 会留空。")

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
            raise AppError("NODE_CONFIG_MISMATCH", "节点不属于当前配置", 400)

        links = self.list_peer_links(config_id)
        reverse_by_group: dict[str, PeerLink] = {}
        for link in links:
            if link.peer_node_id == node_id:
                reverse_by_group[link.link_group_id] = link

        connections: list[dict[str, object]] = []
        for link in links:
            if link.local_node_id != node_id:
                continue
            reverse = reverse_by_group.get(link.link_group_id)
            peer_node = self.get_node(link.peer_node_id)
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
            raise AppError("NODE_CONFIG_MISMATCH", "链路节点不属于当前配置", 400)
        if str(reverse["local_node_id"]) != peer_node.id or str(reverse["peer_node_id"]) != local_node.id:
            raise AppError("INVALID_PEER_LINK", "双向链路节点方向不匹配", 400)
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
                raise AppError("PEER_LINK_NOT_FOUND", "链路组不存在", 404)
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
                raise AppError("PEER_LINK_NOT_FOUND", "链路组不存在", 404)
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
            raise AppError("NODE_STATE_NOT_FOUND", "节点配置状态不存在", 404)
        return _state_from_row(row)

    def get_runtime(self, config_id: str, node_id: str) -> EndpointRuntimeStatus:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM endpoint_runtime_status WHERE config_id = ? AND node_id = ?",
                (config_id, node_id),
            ).fetchone()
        if row is None:
            raise AppError("RUNTIME_NOT_FOUND", "节点运行状态不存在", 404)
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
            summary="命令已记录，等待服务端模拟执行",
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
                raise AppError("CONTROL_LOG_NOT_FOUND", "控制日志不存在", 404)
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
        summary = "已记录控制命令"
        if action == ControlAction.probe:
            updates["connectivity_state"] = ConnectivityState.online.value if runtime.online else ConnectivityState.offline.value
            updates["last_probe_sent_at"] = now.isoformat()
            updates["last_probe_ack_at"] = now.isoformat()
            updates["last_connectivity_reason"] = "server-simulated-probe"
            summary = "已完成探测，结果来自服务端模拟状态"
        elif action == ControlAction.start:
            updates["wg_running"] = 1
            updates["wg_runtime_state"] = WgRuntimeState.running.value
            updates["online"] = 1
            updates["connectivity_state"] = ConnectivityState.online.value
            updates["last_seen"] = now.isoformat()
            summary = "WireGuard 已标记为运行"
        elif action == ControlAction.stop:
            updates["wg_running"] = 0
            updates["wg_runtime_state"] = WgRuntimeState.stopped.value
            updates["online"] = 0
            updates["connectivity_state"] = ConnectivityState.offline.value
            updates["last_connectivity_reason"] = "manual-stop"
            summary = "WireGuard 已标记为停止"
        elif action == ControlAction.restart:
            updates["wg_running"] = 1
            updates["wg_runtime_state"] = WgRuntimeState.running.value
            updates["online"] = 1
            updates["connectivity_state"] = ConnectivityState.online.value
            updates["last_seen"] = now.isoformat()
            summary = "WireGuard 已标记为重启成功"
        elif action == ControlAction.sync:
            self.sync_node(config_id, node_id, requested_by="endpoint-control")
            updates["config_sync_state"] = ConfigSyncState.in_sync.value
            summary = "节点配置已同步到 staged"
        elif action == ControlAction.wg_show:
            summary = "已记录 wg_show 请求，客户端阶段暂缓"
        else:
            raise AppError("INVALID_ACTION", "不支持的控制动作", 400)
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
                if config.auto_sync and node.auto_sync:
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
                        now if config.auto_sync and node.auto_sync else state.staged_updated_at.isoformat() if state.staged_updated_at else None,
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
        node = self.get_node(node_id)
        state = self.get_node_config_state(config_id, node_id)
        runtime = self.get_runtime(config_id, node_id)
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
        preview = self.build_wg_preview(config_id, node_id)
        result = self.save_applied_conf(config_id, node_id, str(preview["content"]))
        state = self.get_node_config_state(config_id, node_id)
        return {"message": "节点配置已同步", "staged_version": state.staged_version, "staged_sha256": state.staged_sha256, "sync_status": result}

    def sync_all(self, config_id: str) -> dict[str, object]:
        synced: list[str] = []
        for node in self.list_nodes(config_id):
            self.sync_node(config_id, node.id, requested_by="sync-all")
            synced.append(node.id)
        return {"message": "全部节点配置已同步", "synced_count": len(synced), "failed_count": 0, "synced": synced, "failed": []}

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

    def read_password(self) -> str:
        with connect() as connection:
            row = connection.execute("SELECT value FROM system_settings WHERE key = 'auth_password_hash'").fetchone()
        return row["value"] if row else "admin123"

    def update_password(self, current_password: str, new_password: str) -> None:
        if self.read_password() != current_password:
            raise AppError("AUTH_FAILED", "当前密码不正确", 401)
        with connect() as connection:
            connection.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'auth_password_hash'", (new_password, now_utc().isoformat()))

    def create_snapshot(self, note: str) -> SnapshotInfo:
        snapshot_id = now_utc().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"snapshot_{snapshot_id}.zip"
        snapshot_path = backups_dir() / snapshot_name
        with ZipFile(snapshot_path, "w", compression=ZIP_DEFLATED) as archive:
            database_path = data_dir() / "wg_free_mesh.db"
            if database_path.exists():
                archive.write(database_path, arcname="data/wg_free_mesh.db")
            for file in wireguard_dir().rglob("*"):
                if file.is_file():
                    archive.write(file, arcname=str(file.relative_to(Path.cwd())))
        snapshot = SnapshotInfo(id=snapshot_id, name=snapshot_name, path=str(snapshot_path), size=snapshot_path.stat().st_size, note=note, created_at=now_utc())
        with connect() as connection:
            connection.execute(
                "INSERT INTO backups (id, name, path, size, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (snapshot.id, snapshot.name, snapshot.path, snapshot.size, snapshot.note, snapshot.created_at.isoformat()),
            )
        return snapshot

    def list_snapshots(self) -> list[SnapshotInfo]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM backups ORDER BY created_at DESC").fetchall()
        return [_snapshot_from_row(row) for row in rows]

    def get_snapshot(self, snapshot_id: str) -> SnapshotInfo:
        with connect() as connection:
            row = connection.execute("SELECT * FROM backups WHERE id = ?", (snapshot_id,)).fetchone()
        if row is None:
            raise AppError("SNAPSHOT_NOT_FOUND", "快照不存在", 404)
        return _snapshot_from_row(row)

    def delete_snapshot(self, snapshot_id: str) -> None:
        snapshot = self.get_snapshot(snapshot_id)
        path = Path(snapshot.path)
        if path.exists():
            path.unlink()
        with connect() as connection:
            connection.execute("DELETE FROM backups WHERE id = ?", (snapshot_id,))

    def update_snapshot_note(self, snapshot_id: str, note: str) -> SnapshotInfo:
        self.get_snapshot(snapshot_id)
        with connect() as connection:
            connection.execute("UPDATE backups SET note = ? WHERE id = ?", (note, snapshot_id))
        return self.get_snapshot(snapshot_id)

    def restore_snapshot(self, snapshot_id: str) -> None:
        self.restore_snapshot_archive(Path(self.get_snapshot(snapshot_id).path))

    def restore_snapshot_archive(self, path: Path) -> None:
        if not path.exists():
            raise AppError("SNAPSHOT_NOT_FOUND", "快照包不存在", 404)
        with ZipFile(path, "r") as archive:
            archive.extractall(Path.cwd())

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
        runtimes = [self.get_runtime(node.config_id, node.id) for node in nodes]
        return {
            "summary": {
                "configs": len(configs),
                "nodes": len(nodes),
                "dynamic_nodes": len([node for node in nodes if node.node_type == NodeType.dynamic]),
                "online_nodes": len([runtime for runtime in runtimes if runtime.online]),
                "pending_sync_nodes": len([runtime for runtime in runtimes if runtime.config_sync_state != ConfigSyncState.in_sync]),
            },
            "services": {"database": "ok", "mqtt": "deferred", "wireguard": "deferred"},
            "timestamp": now_utc(),
        }

    def config_overview(self, config_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        runtimes = self.list_runtime_snapshot(config_id)
        runtime_by_node_id = {str(item["node_id"]): item for item in runtimes}
        return {
            "config": config,
            "stats": {
                "total_nodes": len(nodes),
                "dynamic_nodes": len([node for node in nodes if node.node_type == NodeType.dynamic]),
                "static_nodes": len([node for node in nodes if node.node_type == NodeType.static]),
                "online_nodes": len([item for item in runtimes if item["online"]]),
                "pending_sync_nodes": len([item for item in runtimes if item["config_sync_state"] != ConfigSyncState.in_sync]),
                "peer_links": len(self.list_peer_links(config_id)) // 2,
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
                    "online": bool(runtime_by_node_id.get(node.id, {}).get("online", False)),
                    "peers_total": _int_value(runtime_by_node_id.get(node.id, {}).get("peers_total"), 0),
                }
                for node in nodes
            ],
            "runtime_snapshot": runtimes,
            "sync_status": self.get_sync_status_for_config(config_id),
        }

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
            return f"{peer_node.name} 没有公网 {family.upper()} 入口，自动留空"
        port = peer_node.listen_port or config.default_listen_port
        endpoint = f"[{host}]:{port}" if _is_ipv6_literal(host) else f"{host}:{port}"
        return f"自动使用 {endpoint}"

    def _peer_link_endpoint_summary(self, config: Config, peer_node: Node, link: PeerLink) -> str:
        if link.endpoint_mode == EndpointMode.none:
            return "不写 Endpoint"
        if link.endpoint_mode == EndpointMode.manual:
            host = link.endpoint_manual_host or ""
            port = link.endpoint_manual_port
            if not host or not port:
                return "手动模式需填写 Host 和 Port"
            endpoint = f"[{host}]:{port}" if _is_ipv6_literal(host) else f"{host}:{port}"
            return f"手动使用 {endpoint}"
        family = "ipv6" if link.endpoint_ref_family == EndpointFamily.ipv6 else "ipv4"
        return self._endpoint_preview_text(config, peer_node, family)

    def _draft_endpoint_summary(self, config: Config, peer_node: Node, endpoint_mode: str, family: str, manual_host: str | None, manual_port: int | None) -> str:
        if endpoint_mode == EndpointMode.none.value:
            return "不写 Endpoint"
        if endpoint_mode == EndpointMode.manual.value:
            if not manual_host or not manual_port:
                return "手动模式需填写 Host 和 Port"
            endpoint = f"[{manual_host}]:{manual_port}" if _is_ipv6_literal(manual_host) else f"{manual_host}:{manual_port}"
            return f"手动使用 {endpoint}"
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
            return "未设置"
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
                "endpoint_summary": "缺少反向连接",
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

    def _validate_endpoint_references(self, config_id: str, current: Node, updated: Node) -> None:
        return None

    def _validate_link_endpoint_settings(
        self,
        payload: dict[str, object],
    ) -> None:
        endpoint_mode = EndpointMode(str(payload.get("endpoint_mode", EndpointMode.auto)))
        if endpoint_mode == EndpointMode.none:
            return
        if endpoint_mode == EndpointMode.manual:
            if not _str_or_none(payload.get("endpoint_manual_host")) or not _int_or_none(payload.get("endpoint_manual_port")):
                raise AppError("INVALID_ENDPOINT", "手动 Endpoint 必须填写 Host 和 Port。", 400)
            return

    def _validate_mesh_payload(self, config_id: str) -> dict[str, object]:
        messages: list[str] = []
        links = self.list_peer_links(config_id)
        nodes = {node.id: node for node in self.list_nodes(config_id)}
        if not links:
            messages.append("当前配置还没有任何 peer link。")
        for link in links:
            if link.local_node_id == link.peer_node_id:
                messages.append(f"节点 {link.local_node_id} 存在自连接。")
            if link.peer_node_id not in nodes:
                messages.append(f"链路 {link.id} 指向不存在的节点。")
            if not link.allowed_ips:
                messages.append(f"链路 {link.id} 缺少 allowed_ips。")
        return {"valid": not messages, "messages": messages or ["拓扑校验通过。"]}

    def _resolve_endpoint(self, config: Config, peer_node: Node, link: PeerLink) -> str | None:
        if link.endpoint_mode == "none":
            return None
        host = link.endpoint_manual_host if link.endpoint_mode == "manual" else self._endpoint_host_for_family(peer_node, link.endpoint_ref_family)
        if not host:
            return None
        port = link.endpoint_manual_port if link.endpoint_port_mode == "manual" else peer_node.listen_port or config.default_listen_port
        if not port:
            return None
        return f"[{host}]:{port}" if _is_ipv6_literal(host) else f"{host}:{port}"

    def _conf_path(self, config_id: str, node_id: str) -> Path:
        target = wireguard_dir() / config_id
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{node_id}.conf"

    def _write_service_conf(self, config_id: str, node_id: str, content: str) -> None:
        self._conf_path(config_id, node_id).write_text(content, encoding="utf-8")


store = SQLiteStore()
