from datetime import datetime

from pydantic import BaseModel, Field


class ConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)


class ConfigRead(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    virtual_subnet: str
    default_listen_port: int
    default_mtu: int | None
    default_dns: str | None
    auto_sync: bool
    node_count: int
    dynamic_node_count: int = 0
    online_node_count: int = 0
    offline_node_count: int = 0
    disabled_node_count: int = 0
    topology_invalid: bool = False
    topology_error_count: int = 0
    created_at: datetime
    updated_at: datetime
