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
            messages.append("至少需要两个端点才能形成 Mesh。")

        static_count = sum(1 for node in nodes if node.node_type == NodeType.static)
        if static_count == 0:
            messages.append("建议至少保留一个静态端点。")
        if not links:
            messages.append("当前配置还没有 peer link。")

        if not messages:
            messages.append("基础拓扑检查通过。")

        return MeshValidationRead(valid=len(nodes) >= 2 and static_count >= 1 and bool(links), messages=messages)


mesh_service = MeshService()
