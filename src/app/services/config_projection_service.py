from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.models import now_utc
from app.data.store import store


@dataclass(slots=True)
class ConfigProjectionSnapshot:
    config_id: str
    overview: dict[str, Any]
    tags: list[dict[str, Any]]
    generated_at: datetime = field(default_factory=now_utc)


class ConfigProjectionService:
    def build(self, config_id: str) -> ConfigProjectionSnapshot:
        overview = store.config_overview(config_id)
        tags = store.list_tags(config_id)
        return ConfigProjectionSnapshot(config_id=config_id, overview=overview, tags=tags)


config_projection_service = ConfigProjectionService()

