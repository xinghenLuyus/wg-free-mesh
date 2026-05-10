from __future__ import annotations

from typing import Literal

from app.core.errors import AppError
from app.core.config import settings
from app.domain.models import NodeType
from app.repositories.sqlite import store

MqttAction = Literal["publish", "subscribe"]


class MqttAuthService:
    def node_username(self, node_id: str) -> str:
        return node_id

    def node_client_id(self, node_id: str) -> str:
        return f"wfm-{node_id}"

    def allowed_topics(self, config_id: str, node_id: str) -> dict[str, tuple[str, ...]]:
        prefix = f"wfm/{config_id}/{node_id}"
        return {
            "subscribe": (
                f"{prefix}/config/push",
                f"{prefix}/control",
                f"{prefix}/detect",
                f"{prefix}/info",
            ),
            "publish": (
                f"{prefix}/config/push/ack",
                f"{prefix}/control/ack",
                f"{prefix}/detect/ack",
                f"{prefix}/info/ack",
                f"{prefix}/event",
                f"{prefix}/heartbeat",
            ),
        }

    def authz_decision(
        self,
        *,
        username: str,
        client_id: str,
        topic: str,
        action: MqttAction,
    ) -> bool:
        if username == settings.emqx_username:
            return True
        try:
            node = store.get_node(username)
            config = store.get_config(node.config_id)
        except AppError:
            return False
        if node.node_type != NodeType.dynamic or not node.enabled:
            return False
        if not config.enabled:
            return False
        if client_id != self.node_client_id(node.id):
            return False
        topic_map = self.allowed_topics(config.id, node.id)
        return topic in topic_map[action]


mqtt_auth_service = MqttAuthService()
