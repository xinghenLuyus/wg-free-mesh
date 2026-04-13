from app.domain.models import Node, NodeRole
from app.repositories.sqlite import store


class NodeService:
    def list_nodes(self, config_id: str | None = None) -> list[Node]:
        return store.list_nodes(config_id)

    def create_node(self, config_id: str, name: str, address: str, role: NodeRole) -> Node:
        return store.create_node(config_id, name, address, role)


node_service = NodeService()
