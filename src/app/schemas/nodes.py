from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.models import NodeRole, NodeStatus


class NodeCreate(BaseModel):
    config_id: str
    name: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=3, max_length=64)
    role: NodeRole = NodeRole.edge


class NodeRead(BaseModel):
    id: str
    config_id: str
    name: str
    role: NodeRole
    address: str
    status: NodeStatus
    updated_at: datetime

