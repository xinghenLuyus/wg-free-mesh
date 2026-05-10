from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.models import NodeType


class NodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    listen_port: int | None = Field(default=None, ge=1, le=65535)
    virtual_ip: str | None = None
    mtu: int | None = Field(default=None, ge=576, le=65535)
    dns: str | None = None
    auto_sync: bool = True
    enabled: bool = True
    node_type: NodeType = NodeType.dynamic
    public_key: str | None = None
    private_key: str | None = None
    tags: list[str] = Field(default_factory=list)


class NodeRead(BaseModel):
    id: str
    config_id: str
    name: str
    ipv4_address: str | None
    ipv6_address: str | None
    listen_port: int | None
    virtual_ip: str | None
    mtu: int | None
    dns: str | None
    auto_sync: bool
    enabled: bool
    node_type: NodeType
    public_key: str
    private_key: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime
