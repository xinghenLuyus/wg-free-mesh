from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class McpConfigPayload(BaseModel):
    name: str = Field(description="Human-readable Mesh configuration name.", examples=["mesh-main"])
    description: str = Field(default="", description="Optional description shown in the control console.")
    enabled: bool = Field(default=True, description="Whether this configuration participates in normal runtime projections.")
    virtual_subnet: str = Field(default="10.66.0.0/24", description="Default virtual subnet used for IP suggestions and hub-spoke routes.")
    default_listen_port: int = Field(default=51820, ge=1, le=65535, description="Default listen port for nodes without an override.")
    default_mtu: int | None = Field(default=None, ge=576, le=65535, description="Optional default MTU for generated configs.")
    default_dns: str | None = Field(default=None, description="Optional default DNS value for generated configs.")
    auto_sync: bool = Field(default=True, description="Default auto-sync value for newly created nodes only.")
    tunnel_protocol: Literal["wireguard", "amneziawg_2"] = Field(
        default="wireguard",
        description="Tunnel protocol for generated configs. Use amneziawg_2 only when endpoints have AWG tooling.",
    )
    awg_s1: int | None = Field(default=None, description="AmneziaWG S1 config-level obfuscation value. Leave empty for backend random.")
    awg_s2: int | None = Field(default=None, description="AmneziaWG S2 config-level obfuscation value. Leave empty for backend random.")
    awg_s3: int | None = Field(default=None, description="AmneziaWG S3 config-level obfuscation value. Leave empty for backend random.")
    awg_s4: int | None = Field(default=None, description="AmneziaWG S4 config-level obfuscation value. Leave empty for backend random.")
    awg_h1: str | None = Field(default=None, description="AmneziaWG H1 header value or range. Leave empty for backend random.")
    awg_h2: str | None = Field(default=None, description="AmneziaWG H2 header value or range. Leave empty for backend random.")
    awg_h3: str | None = Field(default=None, description="AmneziaWG H3 header value or range. Leave empty for backend random.")
    awg_h4: str | None = Field(default=None, description="AmneziaWG H4 header value or range. Leave empty for backend random.")


class McpNodePayload(BaseModel):
    name: str = Field(description="Human-readable endpoint name.", examples=["edge-node-1"])
    ipv4_address: str | None = Field(default=None, description="Public IPv4 address or DNS name for auto Endpoint generation.")
    ipv6_address: str | None = Field(default=None, description="Public IPv6 address or DNS name for auto Endpoint generation.")
    listen_port: int | None = Field(default=None, ge=1, le=65535, description="Optional node-specific listen port.")
    virtual_ip: str | None = Field(default=None, description="WireGuard/AmneziaWG virtual IP for this endpoint.")
    mtu: int | None = Field(default=None, ge=576, le=65535, description="Optional node-specific MTU.")
    dns: str | None = Field(default=None, description="Optional node-specific DNS setting.")
    auto_sync: bool | None = Field(default=None, description="Whether this node automatically syncs system state to staged config.")
    enabled: bool | None = Field(default=None, description="Soft enable flag. Disabled nodes are kept but excluded from runtime/sync.")
    node_type: Literal["dynamic", "static"] = Field(default="dynamic", description="dynamic uses WFM client/MQTT; static is manually managed.")
    public_key: str | None = Field(default=None, description="Optional public key. Leave empty when backend should generate key material.")
    private_key: str | None = Field(default=None, description="Optional private key. Handle carefully; it is sensitive.")
    tags: list[str] = Field(default_factory=list, description="Optional node tags.")
    pre_up: list[str] = Field(default_factory=list, description="wg-quick/awg-quick PreUp lifecycle commands.")
    post_up: list[str] = Field(default_factory=list, description="wg-quick/awg-quick PostUp lifecycle commands.")
    pre_down: list[str] = Field(default_factory=list, description="wg-quick/awg-quick PreDown lifecycle commands.")
    post_down: list[str] = Field(default_factory=list, description="wg-quick/awg-quick PostDown lifecycle commands.")
    awg_jc: int | None = Field(default=None, description="AmneziaWG node-local Jc value. Leave empty for backend random.")
    awg_jmin: int | None = Field(default=None, description="AmneziaWG node-local Jmin value. Leave empty for backend random.")
    awg_jmax: int | None = Field(default=None, description="AmneziaWG node-local Jmax value. Leave empty for backend random.")
    awg_i1: str | None = Field(default=None, description="AmneziaWG node-local I1 CPS string. Leave empty for backend random.")
    awg_i2: str | None = Field(default=None, description="AmneziaWG node-local I2 CPS string. Leave empty for backend random.")
    awg_i3: str | None = Field(default=None, description="AmneziaWG node-local I3 CPS string. Leave empty for backend random.")
    awg_i4: str | None = Field(default=None, description="AmneziaWG node-local I4 CPS string. Leave empty for backend random.")
    awg_i5: str | None = Field(default=None, description="AmneziaWG node-local I5 CPS string. Leave empty for backend random.")


class McpPeerLinkDirectionPayload(BaseModel):
    local_node_id: str = Field(description="Node id for this side of the direction.")
    peer_node_id: str = Field(description="Peer node id for the opposite side.")
    allowed_ips: str = Field(description="AllowedIPs written for this direction, usually the peer virtual IP or routed subnet.")
    persistent_keepalive: int | None = Field(default=None, ge=0, le=65535, description="Optional PersistentKeepalive seconds.")
    preshared_key: str | None = Field(default=None, description="Optional direction-level PSK value.")
    endpoint_mode: Literal["auto", "none", "manual"] = Field(default="auto", description="Endpoint generation mode.")
    endpoint_ref_family: Literal["ipv4", "ipv6"] | None = Field(default="ipv4", description="Public address family used by auto mode.")
    endpoint_manual_host: str | None = Field(default=None, description="Manual Endpoint host when endpoint_mode is manual.")
    endpoint_port_mode: Literal["ref_peer_listen_port", "manual"] = Field(
        default="ref_peer_listen_port",
        description="Use peer listen port automatically, or a manual port.",
    )
    endpoint_manual_port: int | None = Field(default=None, ge=1, le=65535, description="Manual Endpoint port.")
    notes: str = Field(default="", description="Optional direction note.")
    enabled: bool = Field(default=True, description="Whether this direction is active.")


class McpPeerLinkGroupPayload(BaseModel):
    forward: McpPeerLinkDirectionPayload = Field(description="Forward direction, typically current node to peer.")
    reverse: McpPeerLinkDirectionPayload = Field(description="Reverse direction, typically peer back to current node.")
    preshared_key: str | None = Field(default=None, description="Optional group PSK copied to both directions.")
    notes: str = Field(default="", description="Optional group note.")
    enabled: bool = Field(default=True, description="Whether the bidirectional Mesh pair is active.")


class McpQuickMeshPayload(BaseModel):
    mode: Literal["hub_spoke", "full_mesh", "free_mesh"] = Field(
        description="Quick-networking mode. hub_spoke uses one gateway, full_mesh connects all nodes, free_mesh supports multiple gateways."
    )
    endpoint_ref_family: Literal["ipv4", "ipv6"] = Field(
        default="ipv4",
        description="Public address family used for generated Endpoint references.",
    )
    hub_node_id: str | None = Field(default=None, description="Gateway node id for hub_spoke mode.")
    gateway_node_ids: list[str] = Field(default_factory=list, description="Gateway node ids for free_mesh mode.")
    leaf_assignments: dict[str, str] = Field(
        default_factory=dict,
        description="free_mesh leaf assignment map: leaf node id -> gateway node id.",
    )
    use_preshared_key: bool = Field(default=False, description="Whether generated Mesh pairs should include PSK.")


class McpPortForwardRulePayload(BaseModel):
    from_node_id: str = Field(description="Service-side node id. Traffic is forwarded from source port toward this node's service.")
    from_port: int = Field(ge=1, le=65535, description="Service-side destination port.")
    to_node_id: str = Field(description="Forwarding entrypoint node id. Managed lifecycle hooks are written here.")
    to_port: int = Field(ge=1, le=65535, description="Source/exposed port on the forwarding entrypoint.")
    to_platform: Literal["linux", "darwin"] = Field(description="Destination hook platform for generated lifecycle commands.")
    protocol: Literal["tcp", "udp", "all"] = Field(default="tcp", description="Protocol to forward; all creates TCP and UDP commands.")


class McpClientArtifactPayload(BaseModel):
    source: Literal["local_build", "github_release"] = Field(
        description="Client artifact source. github_release returns the matching GitHub Release download URL for the current server version."
    )
    goos: Literal["windows", "linux", "darwin"] = Field(description="Target operating system.")
    goarch: Literal["amd64", "arm64", "386"] = Field(description="Target architecture. 386 is Windows-only.")


class McpConfigBulkPackagePayload(BaseModel):
    config_id: str = Field(description="Configuration id whose staged configs should be packaged.")
    node_ids: list[str] = Field(description="Node ids to include in the package.")


class SnapshotExportSelection(BaseModel):
    snapshot_id: str = Field(description="Snapshot id to export. Use read_snapshots to discover available ids.")
