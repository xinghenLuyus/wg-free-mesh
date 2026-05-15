from app.domain.models import Node
from app.data.store import store


class NodeService:
    def list_nodes(self, config_id: str) -> list[Node]:
        return store.list_nodes(config_id)

    def create_node(self, config_id: str, payload: dict[str, object]) -> Node:
        return store.create_node(config_id, payload)


node_service = NodeService()
