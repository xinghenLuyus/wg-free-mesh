from app.domain.models import NodeType, PeerLink
from app.repositories.sqlite import store
from app.schemas.mesh import MeshValidationRead


class MeshService:
    def list_links(self, config_id: str) -> list[PeerLink]:
        return store.list_peer_links(config_id)

    def validate_mesh(self, config_id: str) -> MeshValidationRead:
        nodes = store.list_nodes(config_id)
        links = store.list_peer_links(config_id)
        messages: list[str] = []
        if len(nodes) < 2:
            messages.append("At least two endpoints are required to form a Mesh.")

        static_count = sum(1 for node in nodes if node.node_type == NodeType.static)
        if static_count == 0:
            messages.append("At least one static endpoint is recommended.")
        if not links:
            messages.append("Current config has no peer links.")

        if not messages:
            messages.append("Basic topology check passed.")

        return MeshValidationRead(valid=len(nodes) >= 2 and static_count >= 1 and bool(links), messages=messages)


mesh_service = MeshService()
