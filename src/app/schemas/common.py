from datetime import datetime

from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime


class OperationResult(BaseModel):
    accepted: bool
    message: str

