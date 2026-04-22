# services

`services/` 保存应用服务和用例编排。

## 当前内容

- `auth_service.py`
  - `AuthService`：管理员初始化、登录、修改密码、后台 token、下载 token 与 bootstrap 重置。
  - `CurrentUser` / `DownloadGrant`：认证后的授权载体。
- `control_plane_service.py`
  - `ControlPlaneService`：控制平面主服务，统一编排配置、节点、Mesh、同步态、运行态、快照、MQTT 设置，并把实时发布委托给统一发布计划。
- `topology_service.py`
  - `TopologyService`：负责 Mesh 连接完整性、拓扑校验和系统级拓扑摘要，不再把这部分规则散落在仓储和 Router 中。
- `config_service.py`
  - `ConfigService`：配置相关兼容入口。
- `node_service.py`
  - `NodeService`：节点相关兼容入口。
- `mesh_service.py`
  - `MeshService`：Mesh 相关兼容入口。
- `endpoint_service.py`
  - `EndpointService`：端点控制与运行态兼容入口。
- `realtime_service.py`
  - `RealtimeService`：SSE 发布、订阅与连接管理。
  - `startup()`：应用启动时重置实时服务状态。
  - `shutdown()`：应用退出时主动唤醒并结束所有订阅，避免浏览器长连接阻塞后端停机。

## 约定

- 服务层承接业务动作，前端不承担批量一致性逻辑。
- 拓扑规则属于服务层真相，首页、侧栏、系统状态页和配置页都必须共享同一份拓扑判断。
- 标签创建、删除、批量应用和端点归属变更由后端服务完成。
- 旧模型名不得继续出现在服务层，例如 `NodeRole`、`NodeStatus`、`MeshLink`。
- 修改服务层后需要通过 `mypy app`。
- 实时服务必须保证后端停机时可主动收口，不允许把 SSE 连接的关闭完全寄托在浏览器先断开。
