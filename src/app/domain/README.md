# domain

`domain/` 保存领域模型和领域规则。

## 当前内容

- `models.py`
  - 保存 `Config`、`Node`、`PeerLink`、`SnapshotInfo` 等核心领域模型。
  - 保存 `NodeType`、`EndpointMode`、`ConnectivityState`、`ControlAction` 等领域枚举。
  - 保存 WireGuard 密钥生成、时间戳与 ID 生成等领域级辅助函数。

## 约定

- 不依赖 FastAPI、数据库和外部服务。
- 后续 WireGuard、Mesh、同步状态等核心规则优先沉淀到这里。
