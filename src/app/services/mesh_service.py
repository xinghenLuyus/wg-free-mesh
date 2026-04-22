from app.domain.models import PeerLink
from app.repositories.sqlite import store
from app.schemas.mesh import MeshValidationRead


class MeshService:
    def list_links(self, config_id: str) -> list[PeerLink]:
        return store.list_peer_links(config_id)

    def validate_mesh(self, config_id: str) -> MeshValidationRead:
        return MeshValidationRead.model_validate(store._validate_mesh_payload(config_id))


mesh_service = MeshService()
