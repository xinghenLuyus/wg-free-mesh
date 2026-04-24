# services

`services/` 保存应用服务和用例编排。

## 当前内容

- `auth_service.py`
  - `AuthService`：管理员初始化、登录、修改密码、后台 token、下载 token 与 bootstrap 重置。
  - `CurrentUser` / `DownloadGrant`：认证后的授权载体。
- `control_plane_service.py`
  - `ControlPlaneService`：控制平面主服务，统一编排配置、节点、Mesh、同步态、运行态、快照、MQTT 设置，并把实时发布委托给统一发布计划。
  - 节点类型切换时负责把“动态节点专属资源”收口到后端：回收 MQTT 凭据、重置客户端状态、把运行态归零，避免静态节点残留在线脏状态。
  - `test_mqtt_settings(...)`：对 MQTT Host、Port、TLS 发起真实 TCP / TLS 连通性测试。
- `snapshot_service.py`
  - `SnapshotService`：负责快照压缩包创建、恢复、导入、导出、备注 manifest 同步和磁盘索引重建。
  - `rebuild_index_from_disk()`：扫描 `data/backups/`，把磁盘快照回填到 `backups` 表，避免恢复后快照元数据丢失。
- `topology_service.py`
  - `TopologyService`：负责 Mesh 连接完整性、拓扑校验和系统级拓扑摘要，不再把这部分规则散落在仓储和 Router 中。
- `emqx_service.py`
  - `EmqxService`：集中管理 EMQX 管理 API 地址、节点 MQTT 凭据写入请求格式和 bind 时下发给客户端的 broker 参数。
- `mqtt_auth_service.py`
  - `MqttAuthService`：统一管理节点 MQTT 用户名、client_id、topic ACL 和 EMQX AuthZ 授权判断。
- `mqtt_ingress_service.py`
  - `MqttIngressService`：服务端高权限 MQTT 客户端，订阅所有客户端上行 topic，处理 `heartbeat`、`event` 和 ACK，并把变化推送到 SSE。
  - 对已经切换为静态节点的 MQTT 上行消息直接忽略，防止旧客户端把静态节点重新写回在线。
  - `status_summary()`：统一返回 MQTT 服务是否启用、是否已连接、最近错误和最近连接时间，供系统状态页和端点能力开关复用。
  - `reconcile()`：在设置页切换 MQTT 服务启停后，按当前配置即时启动或停止 MQTT 入口服务。
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
- 快照备注属于压缩包内 manifest 和数据库元数据的双写内容，修改备注时必须同时更新两处。
