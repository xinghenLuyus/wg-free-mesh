from __future__ import annotations

from app.core.config import settings
from app.domain.models import Node, NodeType


def mqtt_services_enabled() -> bool:
    return bool(settings.enable_mqtt_services)


def effective_node_type(node: Node) -> NodeType:
    return node.node_type if mqtt_services_enabled() else NodeType.static


def effective_node(node: Node) -> Node:
    node_type = effective_node_type(node)
    return node if node.node_type == node_type else node.model_copy(update={"node_type": node_type})
