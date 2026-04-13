from datetime import datetime

from pydantic import BaseModel

from app.domain.models import MeshLinkStatus


class MeshLinkRead(BaseModel):
    id: str
    config_id: str
    source_node_id: str
    target_node_id: str
    status: MeshLinkStatus
    updated_at: datetime

class MeshValidationRead(BaseModel):
    valid: bool
    messages: list[str]

