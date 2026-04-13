from app.schemas.common import OperationResult


class EndpointService:
    def apply_config(self, node_id: str) -> OperationResult:
        return OperationResult(accepted=True, message=f"节点 {node_id} 的配置下发请求已进入队列。")

    def restart(self, node_id: str) -> OperationResult:
        return OperationResult(accepted=True, message=f"节点 {node_id} 的重启请求已进入队列。")


endpoint_service = EndpointService()
