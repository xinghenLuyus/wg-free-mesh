from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def encode_key(raw: bytes) -> str:
    return base64.b64encode(raw).decode("utf-8")


def generate_private_key() -> str:
    return encode_key(secrets.token_bytes(32))


def derive_public_key(private_key: str) -> str:
    digest = hashlib.sha256(private_key.encode("utf-8")).digest()[:32]
    return encode_key(digest)


def generate_key_pair() -> tuple[str, str]:
    private_key = generate_private_key()
    return private_key, derive_public_key(private_key)


class NodeType(StrEnum):
    dynamic = "dynamic"
    static = "static"


class ConnectivityState(StrEnum):
    unknown = "unknown"
    online = "online"
    offline = "offline"
    probing = "probing"


class WgRuntimeState(StrEnum):
    unknown = "unknown"
    running = "running"
    stopped = "stopped"


class ConfigSyncState(StrEnum):
    unknown = "unknown"
    pending = "pending"
    in_sync = "in_sync"
    failed = "failed"


class ControlStatus(StrEnum):
    pending = "pending"
    acked = "acked"
    failed = "failed"
    timeout = "timeout"
    simulated = "simulated"


class EndpointMode(StrEnum):
    none = "none"
    auto = "auto"
    manual = "manual"


class EndpointFamily(StrEnum):
    ipv4 = "ipv4"
    ipv6 = "ipv6"
    domain = "domain"


class EndpointPortMode(StrEnum):
    ref_peer_listen_port = "ref_peer_listen_port"
    manual = "manual"


class ControlAction(StrEnum):
    probe = "probe"
    start = "start"
    stop = "stop"
    restart = "restart"
    wg_show = "wg_show"
    sync = "sync"


class Config(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cfg"))
    name: str
    description: str = ""
    enabled: bool = True
    virtual_subnet: str = "10.66.0.0/24"
    default_listen_port: int = 51820
    default_mtu: int | None = None
    default_dns: str | None = None
    auto_sync: bool = True
    node_count: int = 0
    dynamic_node_count: int = 0
    updated_at: datetime = Field(default_factory=now_utc)
    created_at: datetime = Field(default_factory=now_utc)


class Node(BaseModel):
    id: str = Field(default_factory=lambda: new_id("node"))
    config_id: str
    name: str
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    listen_port: int | None = None
    virtual_ip: str | None = None
    mtu: int | None = None
    dns: str | None = None
    auto_sync: bool = True
    node_type: NodeType = NodeType.dynamic
    public_key: str
    private_key: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PeerLink(BaseModel):
    id: str = Field(default_factory=lambda: new_id("plink"))
    config_id: str
    local_node_id: str
    peer_node_id: str
    link_group_id: str
    direction: str
    enabled: bool = True
    allowed_ips: str
    persistent_keepalive: int | None = None
    preshared_key: str | None = None
    endpoint_mode: EndpointMode = EndpointMode.auto
    endpoint_ref_family: EndpointFamily | None = EndpointFamily.ipv4
    endpoint_manual_host: str | None = None
    endpoint_port_mode: EndpointPortMode = EndpointPortMode.ref_peer_listen_port
    endpoint_manual_port: int | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class NodeConfigState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ncs"))
    config_id: str
    node_id: str
    desired_text: str = ""
    desired_sha256: str = ""
    desired_version: int = 0
    staged_text: str = ""
    staged_sha256: str = ""
    staged_version: int = 0
    confirmed_text: str = ""
    confirmed_sha256: str = ""
    confirmed_version: int = 0
    reported_local_sha256: str = ""
    reported_local_version: int = 0
    desired_generated_at: datetime | None = None
    staged_updated_at: datetime | None = None
    confirmed_updated_at: datetime | None = None
    updated_at: datetime = Field(default_factory=now_utc)
    created_at: datetime = Field(default_factory=now_utc)


class EndpointRuntimeStatus(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rt"))
    config_id: str
    node_id: str
    online: bool = False
    connectivity_state: ConnectivityState = ConnectivityState.unknown
    wg_running: bool = False
    wg_runtime_state: WgRuntimeState = WgRuntimeState.unknown
    config_sync_state: ConfigSyncState = ConfigSyncState.unknown
    peers_online: int = 0
    peers_total: int = 0
    last_seen: datetime | None = None
    last_probe_sent_at: datetime | None = None
    last_probe_ack_at: datetime | None = None
    last_control_channel_seen_at: datetime | None = None
    last_config_sync_error: str = ""
    last_connectivity_reason: str = ""
    client_downloaded: bool = False
    client_downloaded_at: datetime | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class EndpointControlLog(BaseModel):
    id: str = Field(default_factory=lambda: new_id("elog"))
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    config_id: str
    node_id: str
    action: ControlAction
    status: ControlStatus = ControlStatus.pending
    requested_by: str = "admin"
    summary: str = ""
    detail: str = ""
    requested_at: datetime = Field(default_factory=now_utc)
    ack_at: datetime | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PasswordState(BaseModel):
    password_hash: str
    updated_at: datetime = Field(default_factory=now_utc)


class SnapshotInfo(BaseModel):
    id: str
    name: str
    path: str
    size: int
    created_at: datetime
    note: str = ""
