from datetime import datetime

from pydantic import BaseModel

from app.domain.models import EndpointFamily, EndpointMode, EndpointPortMode


class MeshLinkRead(BaseModel):
    id: str
    config_id: str
    local_node_id: str
    peer_node_id: str
    link_group_id: str
    direction: str
    enabled: bool
    allowed_ips: str
    persistent_keepalive: int | None
    preshared_key: str | None
    endpoint_mode: EndpointMode
    endpoint_ref_family: EndpointFamily | None
    endpoint_manual_host: str | None
    endpoint_port_mode: EndpointPortMode
    endpoint_manual_port: int | None
    notes: str
    created_at: datetime
    updated_at: datetime


class MeshValidationRead(BaseModel):
    valid: bool
    messages: list[str]
    errors: list[str] = []
    warnings: list[str] = []
