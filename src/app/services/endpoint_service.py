from app.schemas.common import OperationResult


class EndpointService:
    def apply_config(self, node_id: str) -> OperationResult:
        return OperationResult(accepted=True, message=f"Config delivery request for node {node_id} has been queued.")

    def restart(self, node_id: str) -> OperationResult:
        return OperationResult(accepted=True, message=f"Restart request for node {node_id} has been queued.")


endpoint_service = EndpointService()
