# services

`services/` 保存应用服务和用例编排。

## 当前内容

- `auth_service.py`
  - `AuthService`：管理员初始化、登录、修改密码、后台 token、下载 token 与 bootstrap 重置。
  - `CurrentUser` / `DownloadGrant`：认证后的授权载体。
- `control_plane_service.py`
  - `ControlPlaneService`：控制平面主服务，统一编排配置、节点、Mesh、同步态、运行态、快照、MQTT 设置，并把实时发布委托给统一发布计划。
  - 节点类型切换时负责把“动态节点专属资源”收口到后端：回收 MQTT 凭据、重置客户端状态、把运行态归零，避免静态节点残留在线脏状态。
  - 配置、节点、Mesh 的写操作不再在仓储层内联执行整配置重算，而是交给控制平面的后台重算队列合并调度；同一配置短时间内多次变更会合并成一轮 `refresh_config_state(...) + publish_plan(...)`。
  - 写操作会立即失效对应配置投影；配置重算排队或运行期间，详情读取会绕过旧缓存，避免前端在后台重算完成前读到过期开关状态。
  - `test_mqtt_settings(...)`：对 MQTT Host、Port、TLS 发起真实 TCP / TLS 连通性测试。
- `snapshot_service.py`
  - `SnapshotService`：负责快照压缩包创建、恢复、导入、导出、备注 manifest 同步和磁盘索引重建。
  - `rebuild_index_from_disk()`：扫描 `data/backups/`，把磁盘快照回填到 `backups` 表，避免恢复后快照元数据丢失。
- `topology_service.py`
  - `TopologyService`：负责 Mesh 连接完整性、拓扑校验和系统级拓扑摘要，不再把这部分规则散落在仓储和 Router 中。
  - 同一节点对允许存在多组历史 Peer 连接，但不允许多组连接同时启用；重复启用会直接进入拓扑校验失败。
- `emqx_service.py`
  - `EmqxService`：集中管理 EMQX 管理 API 地址、节点 MQTT 凭据写入请求格式和 bind 时下发给客户端的 broker 参数。
- `mqtt_auth_service.py`
  - `MqttAuthService`：统一管理节点 MQTT 用户名、client_id、topic ACL 和 EMQX AuthZ 授权判断。
- `mqtt_ingress_service.py`
  - `MqttIngressService`：服务端高权限 MQTT 客户端，订阅所有客户端上行 topic，把 `heartbeat`、`event` 和 ACK 交给节点运行态服务统一处理。
  - 对已经切换为静态节点的 MQTT 上行消息直接忽略，防止旧客户端把静态节点重新写回在线。
  - `status_summary()`：统一返回 MQTT 服务是否启用、是否已连接、最近错误和最近连接时间，供系统状态页和端点能力开关复用。
  - `reconcile()`：在设置页切换 MQTT 服务启停后，按当前配置即时启动或停止 MQTT 入口服务。
- `node_runtime_service.py`
  - `NodeRuntimeService`：统一收口节点在线/离线、客户端事件、探测 ACK、控制 ACK 和对应的运行态实时发布。
  - MQTT 入站不再自己直接拼装多组 SSE 事件，避免“写库逻辑”和“页面刷新逻辑”继续耦合。
  - 运行态实时发布默认只发送三类权威快照：`endpoint.status.updated`、`runtime.snapshot.updated`、`system.status.updated`。
- `config_projection_service.py`
  - `ConfigProjectionService`：集中生成单配置投影快照，统一收口 `config_overview + tags`，给后台重算发布链路和系统状态汇总复用。
- `system_projection_service.py`
  - `SystemProjectionService`：基于配置级投影快照汇总系统状态，避免每次 SSE 发布都重新走全库现算。
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
  - 当单个订阅者消费落后导致队列拥塞时，实时服务会主动关闭该订阅，让前端重连并补拉快照，而不是静默丢失后续事件。

## 约定

- 服务层承接业务动作，前端不承担批量一致性逻辑。
- 拓扑规则属于服务层真相，首页、侧栏、系统状态页和配置页都必须共享同一份拓扑判断。
- 标签创建、删除、批量应用和端点归属变更由后端服务完成。
- 旧模型名不得继续出现在服务层，例如 `NodeRole`、`NodeStatus`、`MeshLink`。
- 修改服务层后需要通过 `mypy app`。
- 实时服务必须保证后端停机时可主动收口，不允许把 SSE 连接的关闭完全寄托在浏览器先断开。
- 快照备注属于压缩包内 manifest 和数据库元数据的双写内容，修改备注时必须同时更新两处。
