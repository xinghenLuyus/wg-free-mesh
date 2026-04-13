from app.domain.models import MeshLink
from app.repositories.sqlite import store
from app.schemas.mesh import MeshValidationRead


class MeshService:
    def list_links(self, config_id: str) -> list[MeshLink]:
        return store.list_links(config_id)

    def validate_mesh(self, config_id: str) -> MeshValidationRead:
        nodes = store.list_nodes(config_id)
        messages: list[str] = []
        if len(nodes) < 2:
            messages.append("至少需要两个节点才能形成 Mesh。")

        hub_count = sum(1 for node in nodes if node.role == "hub")
        if hub_count == 0:
            messages.append("建议至少保留一个中心节点。")

        if not messages:
            messages.append("基础拓扑检查通过。")

        return MeshValidationRead(valid=len(nodes) >= 2 and hub_count >= 1, messages=messages)


mesh_service = MeshService()
