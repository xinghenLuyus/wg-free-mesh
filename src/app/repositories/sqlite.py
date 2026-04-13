from __future__ import annotations

import ipaddress
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from sqlite3 import Row
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.errors import AppError
from app.domain.models import (
    Config,
    ConfigSyncState,
    ConnectivityState,
    ControlAction,
    ControlStatus,
    EndpointControlLog,
    EndpointRuntimeStatus,
    Node,
    NodeConfigState,
    NodeType,
    PeerLink,
    SnapshotInfo,
    WgRuntimeState,
    derive_public_key,
    generate_key_pair,
    new_id,
    now_utc,
    sha256_text,
)
from app.infrastructure.database import backups_dir, connect, data_dir, wireguard_dir

CONFIG_NAME_RE = re.compile(r"^[a-zA-Z0-9_=+.-]{1,32}$")
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str) and value.isdigit():
        return bool(int(value))
    return bool(value)


def _json_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _config_from_row(row: Row) -> Config:
    return Config(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        enabled=_bool_value(row["enabled"]),
        virtual_subnet=row["virtual_subnet"],
        default_listen_port=row["default_listen_port"],
        default_mtu=row["default_mtu"],
        default_dns=row["default_dns"],
        auto_sync=_bool_value(row["auto_sync"]),
        node_count=row["node_count"] if "node_count" in row.keys() else 0,
        dynamic_node_count=row["dynamic_node_count"] if "dynamic_node_count" in row.keys() else 0,
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
        updated_at=_parse_datetime(row["updated_at"]) or now_utc(),
    )


def _node_from_row(row: Row) -> Node:
    return Node(
        id=row["id"],
        config_id=row["config_id"],
        name=row["name"],
        ipv4_address=row["ipv4_address"],
        ipv6_address=row["ipv6_address"],
        listen_port=row["listen_port"],
        virtual_ip=row["virtual_ip"],
        mtu=row["mtu"],
        dns=row["dns"],
        auto_sync=_bool_value(row["auto_sync"]),
        node_type=row["node_type"],
        public_key=row["public_key"],
        private_key=row["private_key"],
        tags=_json_list(row["tags_json"]),
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
        updated_at=_parse_datetime(row["updated_at"]) or now_utc(),
    )


def _peer_link_from_row(row: Row) -> PeerLink:
    return PeerLink(
        id=row["id"],
        config_id=row["config_id"],
        local_node_id=row["local_node_id"],
        peer_node_id=row["peer_node_id"],
        link_group_id=row["link_group_id"],
        direction=row["direction"],
        enabled=_bool_value(row["enabled"]),
        allowed_ips=row["allowed_ips"],
        persistent_keepalive=row["persistent_keepalive"],
        preshared_key=row["preshared_key"] or None,
        endpoint_mode=row["endpoint_mode"],
        endpoint_ref_family=row["endpoint_ref_family"] or None,
        endpoint_manual_host=row["endpoint_manual_host"] or None,
        endpoint_port_mode=row["endpoint_port_mode"],
        endpoint_manual_port=row["endpoint_manual_port"],
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
        updated_at=_parse_datetime(row["updated_at"]) or now_utc(),
    )


def _state_from_row(row: Row) -> NodeConfigState:
    return NodeConfigState(
        id=row["id"],
        config_id=row["config_id"],
        node_id=row["node_id"],
        desired_text=row["desired_text"],
        desired_sha256=row["desired_sha256"],
        desired_version=row["desired_version"],
        staged_text=row["staged_text"],
        staged_sha256=row["staged_sha256"],
        staged_version=row["staged_version"],
        confirmed_text=row["confirmed_text"],
        confirmed_sha256=row["confirmed_sha256"],
        confirmed_version=row["confirmed_version"],
        reported_local_sha256=row["reported_local_sha256"],
        reported_local_version=row["reported_local_version"],
        desired_generated_at=_parse_datetime(row["desired_generated_at"]),
        staged_updated_at=_parse_datetime(row["staged_updated_at"]),
        confirmed_updated_at=_parse_datetime(row["confirmed_updated_at"]),
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
        updated_at=_parse_datetime(row["updated_at"]) or now_utc(),
    )


def _runtime_from_row(row: Row) -> EndpointRuntimeStatus:
    return EndpointRuntimeStatus(
        id=row["id"],
        config_id=row["config_id"],
        node_id=row["node_id"],
        online=_bool_value(row["online"]),
        connectivity_state=row["connectivity_state"],
        wg_running=_bool_value(row["wg_running"]),
        wg_runtime_state=row["wg_runtime_state"],
        config_sync_state=row["config_sync_state"],
        peers_online=row["peers_online"],
        peers_total=row["peers_total"],
        last_seen=_parse_datetime(row["last_seen"]),
        last_probe_sent_at=_parse_datetime(row["last_probe_sent_at"]),
        last_probe_ack_at=_parse_datetime(row["last_probe_ack_at"]),
        last_control_channel_seen_at=_parse_datetime(row["last_control_channel_seen_at"]),
        last_config_sync_error=row["last_config_sync_error"],
        last_connectivity_reason=row["last_connectivity_reason"],
        client_downloaded=_bool_value(row["client_downloaded"]),
        client_downloaded_at=_parse_datetime(row["client_downloaded_at"]),
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
        updated_at=_parse_datetime(row["updated_at"]) or now_utc(),
    )


def _log_from_row(row: Row) -> EndpointControlLog:
    return EndpointControlLog(
        id=row["id"],
        request_id=row["request_id"],
        config_id=row["config_id"],
        node_id=row["node_id"],
        action=row["action"],
        status=row["status"],
        requested_by=row["requested_by"],
        summary=row["summary"],
        detail=row["detail"],
        requested_at=_parse_datetime(row["requested_at"]) or now_utc(),
        ack_at=_parse_datetime(row["ack_at"]),
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
        updated_at=_parse_datetime(row["updated_at"]) or now_utc(),
    )


def _snapshot_from_row(row: Row) -> SnapshotInfo:
    return SnapshotInfo(
        id=row["id"],
        name=row["name"],
        path=row["path"],
        size=row["size"],
        note=row["note"],
        created_at=_parse_datetime(row["created_at"]) or now_utc(),
    )


def validate_config_name(name: str) -> None:
    if not CONFIG_NAME_RE.match(name):
        raise AppError("INVALID_CONFIG_NAME", "配置名称不是有效的 WireGuard 隧道名", 400)
    upper_name = name.upper()
    if upper_name in RESERVED_NAMES or upper_name.split(".", 1)[0] in RESERVED_NAMES:
        raise AppError("INVALID_CONFIG_NAME", "配置名称不能使用系统保留名", 400)


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
            default_listen_port=int(payload.get("default_listen_port", 51820)),
            default_mtu=int(payload["default_mtu"]) if payload.get("default_mtu") else None,
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
                "default_listen_port": int(payload.get("default_listen_port", current.default_listen_port)),
                "default_mtu": int(payload["default_mtu"]) if payload.get("default_mtu") else None,
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
        node = Node(
            config_id=config_id,
            name=str(payload["name"]).strip(),
            ipv4_address=str(payload.get("ipv4_address") or "") or None,
            ipv6_address=str(payload.get("ipv6_address") or "") or None,
            listen_port=int(payload["listen_port"]) if payload.get("listen_port") else None,
            virtual_ip=str(payload.get("virtual_ip") or "") or self.suggest_virtual_ip(config_id),
            mtu=int(payload["mtu"]) if payload.get("mtu") else None,
            dns=str(payload.get("dns") or "") or None,
            auto_sync=bool(payload.get("auto_sync", True)),
            node_type=str(payload.get("node_type", NodeType.dynamic)),
            public_key=public_key,
            private_key=private_key,
            tags=[str(item) for item in payload.get("tags", [])],
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
                "ipv4_address": str(payload.get("ipv4_address") or current.ipv4_address or "") or None,
                "ipv6_address": str(payload.get("ipv6_address") or current.ipv6_address or "") or None,
                "listen_port": int(payload["listen_port"]) if payload.get("listen_port") else current.listen_port,
                "virtual_ip": str(payload.get("virtual_ip") or current.virtual_ip or "") or None,
                "mtu": int(payload["mtu"]) if payload.get("mtu") else current.mtu,
                "dns": str(payload.get("dns") or current.dns or "") or None,
                "auto_sync": payload.get("auto_sync", current.auto_sync),
                "node_type": str(payload.get("node_type", current.node_type)),
                "private_key": str(payload.get("private_key") or current.private_key),
                "public_key": str(payload.get("public_key") or current.public_key),
                "tags": [str(item) for item in payload.get("tags", current.tags)],
                "updated_at": now_utc(),
            }
        )
        if payload.get("private_key") and not payload.get("public_key"):
            updated = updated.model_copy(update={"public_key": derive_public_key(updated.private_key)})
        validation = self.validate_virtual_ip(current.config_id, updated.virtual_ip or "", exclude_node_id=node_id)
        if not validation["valid"]:
            raise AppError("INVALID_VIRTUAL_IP", str(validation["warning"]), 400)
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

    def create_peer_link_group(self, config_id: str, payload: dict[str, object]) -> list[PeerLink]:
        self.get_config(config_id)
        local_node = self.get_node(str(payload["local_node_id"]))
        peer_node = self.get_node(str(payload["peer_node_id"]))
        if local_node.config_id != config_id or peer_node.config_id != config_id:
            raise AppError("NODE_CONFIG_MISMATCH", "链路节点不属于当前配置", 400)
        group_id = new_id("group")
        now = now_utc().isoformat()
        rows = [
            {
                "id": new_id("plink"),
                "local_node_id": local_node.id,
                "peer_node_id": peer_node.id,
                "direction": "forward",
                "allowed_ips": normalize_allowed_ips(str(payload["allowed_ips_forward"])),
            },
            {
                "id": new_id("plink"),
                "local_node_id": peer_node.id,
                "peer_node_id": local_node.id,
                "direction": "reverse",
                "allowed_ips": normalize_allowed_ips(str(payload["allowed_ips_reverse"])),
            },
        ]
        with connect() as connection:
            for item in rows:
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
                        int(bool(payload.get("enabled", True))),
                        item["allowed_ips"],
                        int(payload["persistent_keepalive"]) if payload.get("persistent_keepalive") else None,
                        str(payload.get("preshared_key") or "") or None,
                        str(payload.get("endpoint_mode", "auto")),
                        str(payload.get("endpoint_ref_family", "ipv4")) if str(payload.get("endpoint_mode", "auto")) != "none" else None,
                        str(payload.get("endpoint_manual_host") or "") or None,
                        str(payload.get("endpoint_port_mode", "ref_peer_listen_port")),
                        int(payload["endpoint_manual_port"]) if payload.get("endpoint_manual_port") else None,
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
            for row in rows:
                allowed_key = "allowed_ips_forward" if row["direction"] == "forward" else "allowed_ips_reverse"
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
                        normalize_allowed_ips(str(payload.get(allowed_key, row["allowed_ips"]))),
                        int(payload["persistent_keepalive"]) if payload.get("persistent_keepalive") else row["persistent_keepalive"],
                        str(payload.get("preshared_key") or row["preshared_key"] or "") or None,
                        str(payload.get("endpoint_mode", row["endpoint_mode"])),
                        str(payload.get("endpoint_ref_family", row["endpoint_ref_family"] or "")) or None,
                        str(payload.get("endpoint_manual_host") or row["endpoint_manual_host"] or "") or None,
                        str(payload.get("endpoint_port_mode", row["endpoint_port_mode"])),
                        int(payload["endpoint_manual_port"]) if payload.get("endpoint_manual_port") else row["endpoint_manual_port"],
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
            action=action,
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
            if link.persistent_keepalive:
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
            "services": {"database": "ok", "mqtt": "deferred", "wireguard": "server-generated"},
            "timestamp": now_utc(),
        }

    def config_overview(self, config_id: str) -> dict[str, object]:
        config = self.get_config(config_id)
        nodes = self.list_nodes(config_id)
        runtimes = self.list_runtime_snapshot(config_id)
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

    def _resolve_endpoint(self, config: Config, peer_node: Node, link: PeerLink) -> str | None:
        if link.endpoint_mode == "none":
            return None
        host = link.endpoint_manual_host if link.endpoint_mode == "manual" else peer_node.ipv6_address if link.endpoint_ref_family == "ipv6" else peer_node.ipv4_address
        if not host:
            return None
        port = link.endpoint_manual_port if link.endpoint_port_mode == "manual" else peer_node.listen_port or config.default_listen_port
        if not port:
            return None
        return f"[{host}]:{port}" if ":" in host and not host.startswith("[") else f"{host}:{port}"

    def _conf_path(self, config_id: str, node_id: str) -> Path:
        target = wireguard_dir() / config_id
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{node_id}.conf"

    def _write_service_conf(self, config_id: str, node_id: str, content: str) -> None:
        self._conf_path(config_id, node_id).write_text(content, encoding="utf-8")


store = SQLiteStore()
