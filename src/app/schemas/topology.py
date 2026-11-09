"""Public board contract: explicit allowlists, never editable config models."""

from typing import Literal

from pydantic import BaseModel

from app.schemas.mesh import MeshHealthRead


class TopologyConfigRead(BaseModel):
    id: str
    name: str
    enabled: bool
    tunnel_protocol: str
    awg_version: str | None


class TopologyNodeRead(BaseModel):
    id: str
    name: str
    node_type: Literal["static", "dynamic"]
    enabled: bool
    virtual_ip: str | None
    ipv4_address: str | None
    ipv6_address: str | None
    tags: list[str]
    endpoint_state: Literal["offline", "not_started", "online"] | None
    wg_runtime_state: str | None
    config_sync_state: str | None


class TopologyDirectionRead(BaseModel):
    link_id: str
    local_node_id: str
    peer_node_id: str
    allowed_ips: str
    persistent_keepalive: int | None
    endpoint_summary: str
    endpoint_ref_family: str | None


class TopologyConnectionRead(BaseModel):
    id: str
    source: str
    target: str
    enabled: bool
    integrity: bool
    validation_errors: list[str]
    has_preshared_key: bool
    forward: TopologyDirectionRead | None
    reverse: TopologyDirectionRead | None
    health: MeshHealthRead


class TopologyIssueRead(BaseModel):
    group_id: str
    reason: str


class TopologyBoardRead(BaseModel):
    config: TopologyConfigRead
    nodes: list[TopologyNodeRead]
    connections: list[TopologyConnectionRead]
    issues: list[TopologyIssueRead]
    generated_at: str
