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
    node_count: int
    updated_at: datetime

