# API接口设计

本文定义重构阶段新的前后端契约。目标不是照抄旧接口路径，而是在覆盖旧系统主要能力的前提下，统一为更稳定的 REST + SSE 结构。

## 设计原则

- 所有前后端通信统一走 `/api/v1`
- 所有响应统一使用 `{ success, data }` 或 `{ success, error }`
- 先固化契约，再同步修改前后端
- 客户端相关 enrollment、`.wgm`、`/api/client/enroll` 暂缓，不纳入本轮实现
- 强实时场景优先使用 SSE，不依赖高频轮询

## 认证与会话

认证采用三态模型：

- `setup_required`：数据库中没有有效管理员密码，只允许初始化相关接口。
- `anonymous`：系统已初始化，但请求没有有效 Bearer Token。
- `authenticated`：请求携带有效后台会话 Bearer Token，可以访问业务 API。

除健康检查、认证状态、初始化和登录接口外，业务接口默认必须携带后台会话令牌：

```text
Authorization: Bearer <access_token>
```

后台会话令牌与下载令牌分开：

- `session` 令牌：登录后签发，拥有后台全局业务权限。
- `download` 令牌：仅用于下载某个配置下某个节点的同步态配置，默认 5 分钟有效，不能用于创建、修改、删除或其它业务接口。

### `GET /api/v1/auth/state`

- 用途：获取系统初始化状态和当前请求认证状态
- 响应：
  - `setup_required`
  - `authenticated`
  - `username`
  - `display_name`
  - `expires_at`

### `GET /api/v1/system/timezone`

- 用途：返回控制台默认显示时区
- 响应：
  - `timezone`
- 说明：
  - 当前默认值为 `Asia/Shanghai`
  - 前端显示时间时不得再从语言推断时区

### `POST /api/v1/auth/setup`

- 用途：首次设置 `admin` 管理员密码
- 约束：仅当 `setup_required=true` 时可用
- 请求：
  - `password`
  - `locale`：界面语言，当前支持 `zh-CN` 和 `en-US`
- 响应：
  - `setup_required`
  - `authenticated`
  - `username`
  - `display_name`
  - `access_token`
  - `token_type`
  - `expires_at`

### `POST /api/v1/auth/login`

- 用途：登录后台
- 说明：返回的后台会话 token 默认 24 小时后过期，过期后前端会被认证拦截回登录页
- 请求：
  - `username`
  - `password`
- 响应：
  - `setup_required`
  - `authenticated`
  - `username`
  - `display_name`
  - `access_token`
  - `token_type`
  - `expires_at`

### `GET /api/v1/auth/session`

- 用途：校验当前 Bearer Token，并返回当前会话状态

### `POST /api/v1/auth/logout`

- 用途：退出登录

### `POST /api/v1/auth/password`

- 用途：修改后台密码
- 约束：必须已登录
- 请求：
  - `current_password`
  - `new_password`
- 响应：
  - `setup_required`
  - `authenticated`
  - `username`
  - `display_name`
  - `access_token`
  - `token_type`
  - `expires_at`
- 说明：
  - 修改密码后后端轮换 token secret，旧 token 立即失效。
  - 后端会在轮换 secret 后立即签发新的后台会话 token，前端无感替换本地 token。
  - `new_password` 不能与当前密码一致。

### 令牌类型

- `session`：管理员后台会话令牌，权限视为 `["*"]`。
- `download`：下载专用令牌，权限视为 `["config.node.download"]`，并绑定：
  - `config_id`
  - `node_id`

### 认证错误码

- `AUTH_SETUP_REQUIRED`：系统尚未设置初始管理员密码，前端应跳转 `/setup`。
- `AUTH_REQUIRED`：业务接口缺少登录凭证，前端应跳转 `/login`。
- `INVALID_TOKEN`：登录凭证无效。
- `TOKEN_EXPIRED`：登录凭证过期。
- `AUTH_FAILED`：用户名或密码错误。
- `PASSWORD_UNCHANGED`：新密码与当前密码一致。
- `DOWNLOAD_TOKEN_REQUIRED`：缺少下载凭证。
- `INVALID_DOWNLOAD_TOKEN`：下载凭证无效。
- `DOWNLOAD_TOKEN_SCOPE_MISMATCH`：下载凭证与当前节点不匹配。

## 界面偏好

### `GET /api/v1/settings/ui`

- 用途：读取控制台界面偏好
- 响应：
  - `locale`
  - `theme_mode`：`system | light | dark`

### `PUT /api/v1/settings/ui`

- 用途：更新控制台界面偏好
- 请求：
  - `locale`
  - `theme_mode`

## 开发测试接口

`/api/v0` 仅用于开发和联调，不参与正式业务契约，不允许前端业务页面依赖。

### `POST /api/v0/dev/reset-bootstrap`

- 用途：一键清空初始化态，重新触发 setup 流程
- 认证：不要求后台登录 token，允许命令行直接调用
- 开关：默认关闭，仅在 `WFM_ENABLE_DEV_TEST_API=true` 时注册
- 清理范围：
  - 管理员密码哈希
  - 登录 token secret
  - 密码更新时间
  - `ui_locale`
  - `ui_theme_mode`
- 不清理：
  - 配置
  - 节点
  - Mesh 关系
  - 业务快照

## 配置管理

### `GET /api/v1/configs`

- 用途：获取配置列表
- 返回补充：
  - `topology_invalid`
  - `topology_error_count`

说明：

- 首页配置卡片和左侧配置列表直接使用这里返回的拓扑异常标记。
- 如果配置已停用，列表层不再上浮其拓扑异常，前端只显示停用状态。
- 前端不得自行遍历 Mesh 连接去推断配置是否异常。

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
- 约束：
  - `virtual_subnet` 必须是合法的 CIDR 网段字符串

### `GET /api/v1/configs/{config_id}`

- 用途：获取单个配置详情

### `PUT /api/v1/configs/{config_id}`

- 用途：更新配置
- 响应会额外返回：
  - `change_hints`
  - `affected_node_ids`

说明：

- `virtual_subnet` 当前仅作为推荐虚拟 IP 的来源，不再作为节点虚拟 IP 的硬性限制边界。
- 为了保证推荐虚拟 IP 能力稳定可用，`virtual_subnet` 仍必须保存为合法的 CIDR 网段字符串。
- 当 `default_listen_port` 变更导致一批端点需要按默认端口重算时，后端会通过 `change_hints` 返回提示信息。

### `DELETE /api/v1/configs/{config_id}`

- 用途：删除配置

### `GET /api/v1/configs/{config_id}/overview`

- 用途：获取配置页总览
- 返回：
  - 配置详情
  - 节点统计
  - 节点完整列表
  - 节点卡片视图模型
  - 拓扑异常摘要
  - 实时状态聚合
  - 同步状态聚合

说明：

- 配置概览页的节点卡片所需在线状态、Peer 数等聚合字段由后端返回。
- 节点卡片额外返回 `mesh_error`，用于标记当前节点是否处于会触发拓扑失败的 Mesh 异常中。
- 配置概览额外返回 `topology`，用于驱动配置头部异常态展示。
- 前端可以做本页临时筛选和排序，但不得自己拼接业务视图模型。

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

说明：

- `ipv4_address` 表示公网 IPv4 入口，可填写 IP 或域名。
- `ipv6_address` 表示公网 IPv6 入口，可填写 IP 或域名。
- 前端不得把二者合并成单个“公网端点”字段。

### `GET /api/v1/nodes/{node_id}`

- 用途：获取单个节点详情

### `PUT /api/v1/nodes/{node_id}`

- 用途：更新节点
- 响应会额外返回：
  - `change_hints`
  - `affected_node_ids`

说明：

- 节点更新会经过后端依赖钩子，扫描受影响的 Mesh 连接。
- 节点设置中的基础字段和 `tags` 应通过同一次 `PUT /api/v1/nodes/{node_id}` 保存，避免前端拆成多次请求造成部分成功、部分失败。
- 当公网入口或监听端口变化导致相关 auto Endpoint 重算时，后端会同步清空已失效的 `persistent_keepalive`。
- 当 `virtual_ip` 变更时，后端不会自动改写 `allowed_ips`，只会返回提示，由用户手工确认。

### `DELETE /api/v1/nodes/{node_id}`

- 用途：删除节点

### `GET /api/v1/configs/{config_id}/tags`

- 用途：获取当前配置的标签列表和使用数量

### `POST /api/v1/configs/{config_id}/tags`

- 用途：在当前配置下创建标签
- 请求：`{ name }`

### `POST /api/v1/configs/{config_id}/tags/apply`

- 用途：批量给端点应用标签
- 请求：`{ tag, node_ids }`
- 约束：后端校验端点必须属于当前配置，前端不负责批量业务一致性

### `DELETE /api/v1/configs/{config_id}/tags/{tag_name}`

- 用途：删除配置标签，并从当前配置下所有端点移除该标签

### `PUT /api/v1/nodes/{node_id}/tags`

- 用途：替换单个端点的所属标签
- 请求：`{ tags }`

### `DELETE /api/v1/nodes/{node_id}/tags/{tag_name}`

- 用途：从单个端点移除一个标签

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

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/mesh-workspace`

- 用途：获取当前节点 Mesh 网络页面所需的后端聚合视图
- 返回：
  - `node`
  - `connections`
  - `validation`

说明：

- `connections` 按 `link_group_id` 聚合双向连接。
- 每个连接包含对端节点、启用状态、PSK 是否配置、备注、更新时间、主向参数和反向参数。
- 主向表示当前节点到对端节点，反向表示对端节点到当前节点。
- 每个连接额外返回：
  - `integrity_status`：`healthy | broken`
  - `integrity_message`
- 前端不得自行从两条 peer link 拼接 Mesh 连接卡片。

说明补充：

- 当一组 Mesh 双向连接在需要 Endpoint 的情况下两侧都无法解析公网入口时，后端会把该连接标记为 `broken`。
- `broken` 连接不自动删除，而是保留参数、前端显示红色标签，并由拓扑校验报错。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/peer-link-draft`

- 用途：获取当前节点新建 Mesh 连接所需的后端业务草稿
- 查询参数：
  - `peer_node_id`
  - `endpoint_ref_family`：`ipv4` 或 `ipv6`
- 返回：
  - `local_node`
  - `peer_node`
  - `endpoint_ref_family`
  - `forward`
  - `reverse`
  - `warnings`

说明：

- 该接口负责生成正反向默认 `allowed_ips`、Endpoint 自动摘要和缺失项警告。
- 前端不得自行推导新建连接的业务默认值。
- 该接口后续可被外部 API 和 MCP 聚合器复用。

### `POST /api/v1/configs/{config_id}/peer-links`

- 用途：创建双向 peer link
- 请求：
  - `forward.local_node_id`
  - `forward.peer_node_id`
  - `forward.allowed_ips`
  - `forward.persistent_keepalive`
  - `forward.endpoint_mode`
  - `forward.endpoint_ref_family`
  - `forward.endpoint_manual_host`
  - `forward.endpoint_manual_port`
  - `reverse.local_node_id`
  - `reverse.peer_node_id`
  - `reverse.allowed_ips`
  - `reverse.persistent_keepalive`
  - `reverse.endpoint_mode`
  - `reverse.endpoint_ref_family`
  - `reverse.endpoint_manual_host`
  - `reverse.endpoint_manual_port`
  - `preshared_key`
  - `notes`
  - `enabled`

说明：

- `endpoint_ref_family` 只使用 `ipv4` 或 `ipv6`，表示自动模式读取对端哪个公网入口。
- 两个公网入口都可以填写 IP 或域名，域名不是独立地址族。
- `endpoint_mode=auto` 表示自动判断对向节点是否有对应公网入口；有则生成 Endpoint，没有则留空。
- `endpoint_mode=none` 表示强制不写 Endpoint。
- `endpoint_mode=manual` 表示手动填写对向 Host 和 Port，不推荐常规场景使用。
- 后端只在 `manual` 模式下强制校验 Host 和 Port。

前端展示时必须使用中文模式名称：

- `auto`：自动
- `none`：不写 Endpoint
- `manual`：手动

创建连接时前端应提交正反向独立配置：

- `forward`：当前节点到对端节点。
- `reverse`：对端节点到当前节点。
- `forward.allowed_ips` 默认使用对端虚拟 IP。
- `reverse.allowed_ips` 默认使用当前节点虚拟 IP。

### `PUT /api/v1/peer-links/{link_group_id}`

- 用途：按 link group 更新双向链路公共属性

### `DELETE /api/v1/peer-links/{link_group_id}`

- 用途：删除双向链路

### `POST /api/v1/peer-links/psk/generate`

- 用途：生成 WireGuard PresharedKey
- 返回：`{ preshared_key }`
- 说明：新建连接和修改连接参数都通过该接口生成 PSK，前端不在浏览器中生成密钥。

### `POST /api/v1/configs/{config_id}/mesh/validate`

- 用途：校验当前配置 mesh 是否存在明显问题
- 响应：
  - `valid`
  - `messages`
  - `errors`
  - `warnings`

说明：

- `errors` 表示真正导致拓扑校验失败的问题。
- `warnings` 表示提示型信息，不会单独让拓扑失败。
- 当前拓扑校验只保留正常业务流里真正有意义的结果：
  - Mesh 连接断裂会进入 `errors`
  - 配置存在节点但还没有任何 Peer 连接会进入 `warnings`
- 那些已经在正常写入链路中被后端业务函数拦住的情况，不再重复由拓扑校验兜底。

同步约束：

- 只要 `mesh/validate` 返回 `valid=false`，该配置下所有节点的系统态到同步态同步都必须视为阻塞状态。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/wg-preview`

- 用途：预览节点 WireGuard 配置

## 配置生成与应用

### `GET /api/v1/configs/{config_id}/sync-status`

- 用途：获取配置下所有节点同步状态

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/sync-status`

- 用途：获取单个节点同步状态
- 返回补充：
  - `topology_valid`
  - `topology_messages`

说明：

- 当 `topology_valid=false` 时，前端必须禁用“自动同步”和“立即同步”入口。
- `topology_messages` 用于直接展示当前阻塞同步的拓扑问题。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`

- 用途：获取服务端已应用配置

### `PUT /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`

- 用途：保存服务端已应用配置

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/download-package`

- 用途：获取下载配置页所需聚合数据
- 返回内容：文件名、同步态配置文本、下载路径

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/download-token`

- 用途：生成当前配置当前节点专用的临时下载令牌
- 鉴权：必须携带后台会话 Bearer Token
- 返回内容：
  - `access_token`
  - `token_type=download`
  - `expires_at`
  - `download_path`
  - `filename`

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/download-conf?download_token=...`

- 用途：直接下载当前节点 `.conf` 文件
- 鉴权：只接受下载专用令牌
- 约束：下载令牌必须匹配当前 `config_id` 和 `node_id`
- 响应：`text/plain`，附带 `Content-Disposition`

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/sync`

- 用途：同步单个节点配置
- 约束：当拓扑校验失败时，后端必须拒绝执行并返回 `TOPOLOGY_INVALID`

### `POST /api/v1/configs/{config_id}/sync-all`

- 用途：同步整个配置下全部节点
- 约束：当拓扑校验失败时，后端必须拒绝执行并返回 `TOPOLOGY_INVALID`

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

### `GET /api/v1/settings/ui`

- 用途：获取当前控制台界面语言
- 响应：
  - `locale`

### `PUT /api/v1/settings/ui`

- 用途：更新当前控制台界面语言
- 请求：
  - `locale`：`zh-CN` 或 `en-US`
- 响应：
  - `locale`

### `GET /api/v1/settings/mqtt`

- 用途：获取客户端 MQTT 公网引导参数
- 返回字段：
  - `host`
  - `port`
  - `tls`
- 说明：
  - 这里只返回客户端可见的公网引导参数
  - 服务端对 EMQX 使用的高权限账号密码不通过该接口暴露

### `PUT /api/v1/settings/mqtt`

- 用途：更新客户端 MQTT 公网引导参数
- 请求字段：
  - `host`
  - `port`
  - `tls`

### `POST /api/v1/settings/mqtt/test`

- 用途：测试 MQTT 连接
- 请求字段：
  - `host`
  - `port`
  - `tls`
- 响应字段：
  - `success`
  - `message`
  - `latency_ms`
- 说明：
  - 后端会真实发起 TCP 连接测试。
  - 当 `tls=true` 时，后端还会继续执行 TLS 握手测试。
  - 该接口测试的是当前后端到目标地址的可达性，不是未来客户端所在机器的网络可达性。

### `POST /api/v1/settings/password`

- 用途：修改后台密码
- 说明：兼容设置域入口，行为和 `POST /api/v1/auth/password` 一致，成功后返回新的后台会话 token。

## 备份恢复

### `POST /api/v1/backups/snapshot`

- 用途：创建快照
- 请求体：原始字符串 `note`
- 说明：
  - 后端会先登记快照元数据，再打包数据库和 WireGuard 目录。
  - 快照包内会写入 manifest，保存快照 id、创建时间和备注。

### `GET /api/v1/backups/list`

- 用途：获取快照列表
- 说明：
  - 列表由后端扫描 `data/backups/` 并重建索引后返回。
  - 恢复快照后，快照记录不会再因为数据库回滚到旧状态而丢失。

### `GET /api/v1/backups/download/{snapshot_id}`

- 用途：下载快照

### `GET /api/v1/backups/export/{snapshot_id}`

- 用途：导出快照
- 说明：与 `download/{snapshot_id}` 等价，前端统一使用导出语义。

### `POST /api/v1/backups/upload`

- 用途：兼容旧路径导入快照包

### `POST /api/v1/backups/import`

- 用途：导入快照包
- 说明：
  - 只导入到快照列表，不自动恢复。
  - 导入时会校验压缩包结构，要求至少包含 `data/wg_free_mesh.db`。

### `POST /api/v1/backups/restore/{snapshot_id}`

- 用途：恢复快照
- 说明：
  - 恢复后后端会重新扫描快照目录并重建 `backups` 表索引。

### `DELETE /api/v1/backups/{snapshot_id}`

- 用途：删除快照

### `PUT /api/v1/backups/{snapshot_id}/note`

- 用途：更新快照备注
- 说明：
  - 修改备注时，后端同时更新数据库元数据和压缩包内 manifest，保证导出、导入、恢复后备注一致。

## 系统状态

### `GET /api/v1/system/health`

- 用途：健康检查

### `GET /api/v1/system/status`

- 用途：系统状态聚合
- 约束：必须已登录
- 返回补充：
  - `topology.valid`
  - `topology.invalid_config_count`
  - `topology.invalid_node_count`
  - `topology.invalid_configs`

说明：

- `system/status` 除了系统健康，还承担全局业务异常摘要。
- 已停用的配置不会再进入系统层拓扑异常统计；这类异常只保留在配置内部查看。
- 左下角系统状态入口和系统状态页都直接消费这里返回的拓扑异常聚合，不在前端二次计算。

## SSE 实时流

### `GET /api/v1/events/stream`

- 用途：订阅后台管理端实时事件
- 约束：请求必须携带有效 Bearer Token
- 协议：SSE
- 当前事件类型：
  - `config.list.updated`
  - `config.overview.updated`
  - `node.workspace.updated`
  - `node.apply.updated`
  - `mesh.workspace.updated`
  - `endpoint.status.updated`
  - `control.log.created`
  - `control.log.updated`
  - `system.status.updated`
  - `system.clock.sync`
  - `settings.mqtt.updated`
  - `snapshot.list.updated`

说明：

- 建立连接后后端应立即推送一次系统状态快照和一次 `system.clock.sync`
- 连接存活期间后端低频推送 `system.clock.sync`
- `system.clock.sync` 同时承担系统时间校时和连接活性信号，不再每秒推流
- 无在线订阅者时，服务端不做空推送
- 系统状态页删除手动刷新按钮，以 SSE 推送和前端本地走秒为准

## 本轮不包含

- Go 客户端实现
- enrollment token 与 `.wgm` 下载
- 真实 MQTT 双向通信闭环
- 真正的 WireGuard 服务启停

以上能力会在本轮接口里预留数据结构和运行位，但不恢复客户端代码。

## 客户端 MQTT 集成补充约束

客户端运行期继续走 MQTT，但推荐集成模式调整为：

- Broker：EMQX
- 账号真相源：`wfm`
- ACL 真相源：`wfm`
- 认证：EMQX 内建账号库
- 授权：EMQX HTTP Authorization 回查 `wfm`

### 客户端 bind 时的返回补充

`POST /api/client/v1/bind` 响应中的 `mqtt` 至少应包含：

- `host`
- `port`
- `tls`
- `username`
- `password`
- `client_id`

说明：

- 由 `wfm` 负责为当前节点生成或轮换专属 MQTT 凭据
- 由 `wfm` 负责把该账号同步到 EMQX
- 一个动态节点只对应一套专属 MQTT 凭据

### EMQX 内部授权接口

#### `POST /api/internal/emqx/authz`

- 用途：供 EMQX 在客户端 publish / subscribe 时回查授权结果
- 不对外开放给前端或客户端

请求核心字段：

- `username`
- `clientid`
- `topic`
- `action`
- 请求头：`x-wfm-internal-key`

响应语义：

- `allow`
- `deny`

约束：

- topic 权限按 `config_id + node_id` 收口
- 客户端只能访问自身节点 topic
- `x-wfm-internal-key` 必须与 `WFM_EMQX_AUTHZ_SHARED_KEY` 一致
- 配置下发与控制命令必须依赖 ACK 才算服务端成功完成
- 状态上报与事件日志属于单向消息，不走 ACK
