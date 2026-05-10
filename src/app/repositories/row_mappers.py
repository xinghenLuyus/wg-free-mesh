from __future__ import annotations

import json
from datetime import datetime
from sqlite3 import Row

from app.domain.models import (
    Config,
    EndpointControlLog,
    EndpointFamily,
    EndpointRuntimeStatus,
    Node,
    NodeConfigState,
    PeerLink,
    SnapshotInfo,
    now_utc,
)


def parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str) and value.isdigit():
        return bool(int(value))
    return bool(value)


def json_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed if str(item).strip()]


def endpoint_family_from_row(value: object) -> EndpointFamily | None:
    if not value:
        return None
    family = str(value)
    if family == "domain":
        family = "ipv4"
    return EndpointFamily.ipv6 if family == "ipv6" else EndpointFamily.ipv4


def config_from_row(row: Row) -> Config:
    return Config(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        enabled=bool_value(row["enabled"]),
        virtual_subnet=row["virtual_subnet"],
        default_listen_port=row["default_listen_port"],
        default_mtu=row["default_mtu"],
        default_dns=row["default_dns"],
        auto_sync=bool_value(row["auto_sync"]),
        node_count=int(row["node_count"] or 0) if "node_count" in row.keys() else 0,
        dynamic_node_count=int(row["dynamic_node_count"] or 0) if "dynamic_node_count" in row.keys() else 0,
        created_at=parse_datetime(row["created_at"]) or now_utc(),
        updated_at=parse_datetime(row["updated_at"]) or now_utc(),
    )


def node_from_row(row: Row) -> Node:
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
        auto_sync=bool_value(row["auto_sync"]),
        node_type=row["node_type"],
        public_key=row["public_key"],
        private_key=row["private_key"],
        tags=json_list(row["tags_json"]),
        created_at=parse_datetime(row["created_at"]) or now_utc(),
        updated_at=parse_datetime(row["updated_at"]) or now_utc(),
    )


def peer_link_from_row(row: Row) -> PeerLink:
    return PeerLink(
        id=row["id"],
        config_id=row["config_id"],
        local_node_id=row["local_node_id"],
        peer_node_id=row["peer_node_id"],
        link_group_id=row["link_group_id"],
        direction=row["direction"],
        enabled=bool_value(row["enabled"]),
        allowed_ips=row["allowed_ips"],
        persistent_keepalive=row["persistent_keepalive"],
        preshared_key=row["preshared_key"] or None,
        endpoint_mode=row["endpoint_mode"],
        endpoint_ref_family=endpoint_family_from_row(row["endpoint_ref_family"]),
        endpoint_manual_host=row["endpoint_manual_host"] or None,
        endpoint_port_mode=row["endpoint_port_mode"],
        endpoint_manual_port=row["endpoint_manual_port"],
        notes=row["notes"],
        created_at=parse_datetime(row["created_at"]) or now_utc(),
        updated_at=parse_datetime(row["updated_at"]) or now_utc(),
    )


def state_from_row(row: Row) -> NodeConfigState:
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
        desired_generated_at=parse_datetime(row["desired_generated_at"]),
        staged_updated_at=parse_datetime(row["staged_updated_at"]),
        confirmed_updated_at=parse_datetime(row["confirmed_updated_at"]),
        created_at=parse_datetime(row["created_at"]) or now_utc(),
        updated_at=parse_datetime(row["updated_at"]) or now_utc(),
    )


def runtime_from_row(row: Row) -> EndpointRuntimeStatus:
    return EndpointRuntimeStatus(
        id=row["id"],
        config_id=row["config_id"],
        node_id=row["node_id"],
        online=bool_value(row["online"]),
        connectivity_state=row["connectivity_state"],
        wg_running=bool_value(row["wg_running"]),
        wg_runtime_state=row["wg_runtime_state"],
        config_sync_state=row["config_sync_state"],
        peers_online=row["peers_online"],
        peers_total=row["peers_total"],
        last_seen=parse_datetime(row["last_seen"]),
        last_probe_sent_at=parse_datetime(row["last_probe_sent_at"]),
        last_probe_ack_at=parse_datetime(row["last_probe_ack_at"]),
        last_control_channel_seen_at=parse_datetime(row["last_control_channel_seen_at"]),
        heartbeat_client_online=bool_value(row["heartbeat_client_online"]),
        heartbeat_wg_online=bool_value(row["heartbeat_wg_online"]),
        detect_client_online=bool_value(row["detect_client_online"]),
        detect_wg_online=bool_value(row["detect_wg_online"]),
        last_config_sync_error=row["last_config_sync_error"],
        last_connectivity_reason=row["last_connectivity_reason"],
        client_downloaded=bool_value(row["client_downloaded"]),
        client_downloaded_at=parse_datetime(row["client_downloaded_at"]),
        created_at=parse_datetime(row["created_at"]) or now_utc(),
        updated_at=parse_datetime(row["updated_at"]) or now_utc(),
    )


def log_from_row(row: Row) -> EndpointControlLog:
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
        requested_at=parse_datetime(row["requested_at"]) or now_utc(),
        ack_at=parse_datetime(row["ack_at"]),
        created_at=parse_datetime(row["created_at"]) or now_utc(),
        updated_at=parse_datetime(row["updated_at"]) or now_utc(),
    )


def snapshot_from_row(row: Row) -> SnapshotInfo:
    return SnapshotInfo(
        id=row["id"],
        name=row["name"],
        path=row["path"],
        size=row["size"],
        note=row["note"],
        created_at=parse_datetime(row["created_at"]) or now_utc(),
    )
