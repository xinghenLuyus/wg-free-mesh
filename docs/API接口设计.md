# API接口设计

本文定义重构阶段新的前后端契约。目标不是照抄旧接口路径，而是在覆盖旧系统主要能力的前提下，统一为更稳定的 REST + WebSocket 结构。

## 设计原则

- 所有前后端通信统一走 `/api/v1`
- 所有响应统一使用 `{ success, data }` 或 `{ success, error }`
- 先固化契约，再同步修改前后端
- 客户端相关 enrollment、`.wgm`、`/api/client/enroll` 暂缓，不纳入本轮实现
- 强实时场景优先使用 WebSocket，不依赖高频轮询

## 认证与会话

### `POST /api/v1/auth/login`

- 用途：登录后台
- 请求：
  - `username`
  - `password`
- 响应：
  - `authenticated`
  - `username`
  - `display_name`

### `GET /api/v1/auth/session`

- 用途：获取当前会话

### `POST /api/v1/auth/logout`

- 用途：退出登录

### `POST /api/v1/settings/password`

- 用途：修改后台密码
- 请求：
  - `current_password`
  - `new_password`

## 配置管理

### `GET /api/v1/configs`

- 用途：获取配置列表

### `POST /api/v1/configs`

- 用途：创建配置
- 请求：
  - `name`
  - `description`
  - `enabled`
  - `virtual_subnet`
  - `default_listen_port`
  - `default_mtu`
  - `default_dns`
  - `auto_sync`

### `GET /api/v1/configs/{config_id}`

- 用途：获取单个配置详情

### `PUT /api/v1/configs/{config_id}`

- 用途：更新配置

### `DELETE /api/v1/configs/{config_id}`

- 用途：删除配置

### `GET /api/v1/configs/{config_id}/overview`

- 用途：获取配置页总览
- 返回：
  - 配置详情
  - 节点统计
  - 实时状态聚合
  - 同步状态聚合

## 节点管理

### `GET /api/v1/configs/{config_id}/nodes`

- 用途：获取配置下节点列表

### `POST /api/v1/configs/{config_id}/nodes`

- 用途：创建节点
- 请求：
  - `name`
  - `node_type`
  - `ipv4_address`
  - `ipv6_address`
  - `listen_port`
  - `virtual_ip`
  - `mtu`
  - `dns`
  - `auto_sync`
  - `public_key`
  - `private_key`
  - `tags`

### `GET /api/v1/nodes/{node_id}`

- 用途：获取单个节点详情

### `PUT /api/v1/nodes/{node_id}`

- 用途：更新节点

### `DELETE /api/v1/nodes/{node_id}`

- 用途：删除节点

### `POST /api/v1/configs/{config_id}/nodes/suggest-ip`

- 用途：推荐虚拟 IP

### `POST /api/v1/configs/{config_id}/nodes/validate-ip`

- 用途：校验虚拟 IP

### `POST /api/v1/nodes/keys/generate`

- 用途：生成 WireGuard 密钥对

### `POST /api/v1/nodes/keys/derive-public`

- 用途：由私钥推导公钥

## Mesh 与 Peer Link

### `GET /api/v1/configs/{config_id}/peer-links`

- 用途：获取配置下所有 peer link

### `POST /api/v1/configs/{config_id}/peer-links`

- 用途：创建双向 peer link
- 请求：
  - `local_node_id`
  - `peer_node_id`
  - `allowed_ips_forward`
  - `allowed_ips_reverse`
  - `persistent_keepalive`
  - `preshared_key`
  - `endpoint_mode`
  - `endpoint_ref_family`
  - `endpoint_manual_host`
  - `endpoint_port_mode`
  - `endpoint_manual_port`
  - `notes`
  - `enabled`

### `PUT /api/v1/peer-links/{link_group_id}`

- 用途：按 link group 更新双向链路公共属性

### `DELETE /api/v1/peer-links/{link_group_id}`

- 用途：删除双向链路

### `POST /api/v1/configs/{config_id}/mesh/validate`

- 用途：校验当前配置 mesh 是否存在明显问题

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/wg-preview`

- 用途：预览节点 WireGuard 配置

## 配置生成与应用

### `GET /api/v1/configs/{config_id}/sync-status`

- 用途：获取配置下所有节点同步状态

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/sync-status`

- 用途：获取单个节点同步状态

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`

- 用途：获取服务端已应用配置

### `PUT /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`

- 用途：保存服务端已应用配置

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/sync`

- 用途：同步单个节点配置

### `POST /api/v1/configs/{config_id}/sync-all`

- 用途：同步整个配置下全部节点

## 端点控制与运行状态

### `GET /api/v1/configs/{config_id}/endpoint/runtime-snapshot`

- 用途：获取当前配置所有节点运行快照

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/status`

- 用途：获取单个节点运行状态

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/logs`

- 用途：获取控制日志

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/control`

- 用途：发送控制命令
- `action`：
  - `probe`
  - `start`
  - `stop`
  - `restart`
  - `wg_show`
  - `sync`

### `POST /api/v1/configs/{config_id}/endpoint/probe-batch`

- 用途：批量探测动态节点

## 设置

### `GET /api/v1/settings/mqtt`

- 用途：获取客户端 MQTT 公网引导参数

### `PUT /api/v1/settings/mqtt`

- 用途：更新客户端 MQTT 公网引导参数

### `POST /api/v1/settings/mqtt/test`

- 用途：测试 MQTT 连接

## 备份恢复

### `POST /api/v1/backups/snapshot`

- 用途：创建快照

### `GET /api/v1/backups/list`

- 用途：获取快照列表

### `GET /api/v1/backups/download/{snapshot_id}`

- 用途：下载快照

### `POST /api/v1/backups/upload`

- 用途：上传快照包

### `POST /api/v1/backups/restore/{snapshot_id}`

- 用途：恢复快照

### `DELETE /api/v1/backups/{snapshot_id}`

- 用途：删除快照

### `PUT /api/v1/backups/{snapshot_id}/note`

- 用途：更新快照备注

## 系统状态

### `GET /api/v1/system/health`

- 用途：健康检查

### `GET /api/v1/system/status`

- 用途：系统状态聚合

## WebSocket

### `GET /api/v1/ws/events`

- 用途：订阅实时事件
- 当前事件类型：
  - `runtime.snapshot.updated`
  - `runtime.node.updated`
  - `control.log.created`
  - `control.log.updated`
  - `sync.status.updated`
  - `system.status.updated`

## 本轮不包含

- Go 客户端实现
- enrollment token 与 `.wgm` 下载
- 真实 MQTT 双向通信闭环
- 真正的 WireGuard 服务启停

以上能力会在本轮接口里预留数据结构和运行位，但不恢复客户端代码。
