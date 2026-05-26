# API接口设计

本文定义当前前后端契约。目标是在覆盖控制平面主要能力的前提下，统一为稳定的 REST + SSE 结构。

## 设计原则

- 所有前后端通信统一走 `/api/v1`
- 所有响应统一使用 `{ success, data }` 或 `{ success, error }`
- 修改接口前先更新契约，再同步修改前后端
- 客户端不再使用注册文件；首次绑定使用 `/api/client/v1/bind`
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
- `download` 令牌：仅用于下载绑定的单个文件，默认 5 分钟有效，不能用于创建、修改、删除或其它业务接口。
  - 节点配置下载令牌绑定 `config_id + node_id`。
  - 文件下载令牌绑定 `kind + resource_id`，当前支持 `client_artifact`、`config_bulk_package`、`snapshot_export`。
  - 下载令牌只校验对应下载接口，不具备后台会话权限。

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
- `download`：下载专用令牌。节点配置下载权限视为 `["config.node.download"]`，并绑定：
  - `config_id`
  - `node_id`
- 文件下载权限视为 `["file.download"]`，并绑定：
  - `kind`
  - `resource_id`

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
  - `online_node_count`
  - `offline_node_count`
  - `disabled_node_count`

说明：

- 首页配置卡片和左侧配置列表直接使用这里返回的拓扑异常标记。
- 如果配置已停用，列表层不再上浮其拓扑异常，前端只显示停用状态。
- 首页网格 / 列表视图直接使用这里返回的节点数量、在线数量、动态节点数量和禁用节点数量。
- `node_count` 包含已禁用端点；`dynamic_node_count`、`online_node_count`、`offline_node_count` 只统计启用动态端点。
- 前端不得自行遍历 Mesh 连接、运行态快照或同步状态去推断配置是否异常、在线节点数或待下发节点数。

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
- `auto_sync` 是新建端点时的默认自动同步开关，不是配置下所有端点的总开关
- `tunnel_protocol` 支持 `wireguard` 和 `amneziawg_2`，默认 `wireguard`。
- `amneziawg_2` 时可传 `awg_s1`-`awg_s4`、`awg_h1`-`awg_h4`；留空由后端随机生成。`H` 字段支持单值或 `start-end` 范围，四组范围不得重叠。

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
- `auto_sync` 只影响后续新建节点的默认值；已有节点是否自动把系统态写入同步态，由节点自己的 `auto_sync` 决定。
- 协议从 `wireguard` 切换到 `amneziawg_2` 时，后端会补齐缺失的配置级 AWG 参数和节点级 AWG 本地参数；从 `amneziawg_2` 切回 `wireguard` 时，后端会清空所有 AWG 专属字段，但保留端点 hook 命令。
- 当 `default_listen_port` 变更导致一批端点需要按默认端口重算时，后端会通过 `change_hints` 返回提示信息。
- `POST /api/v1/configs/awg/random` 返回一组配置级 AWG 随机参数，供创建配置和配置设置页复用。

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
- 节点卡片额外返回 `enabled`。`node_cards` 只包含启用端点，`disabled_node_cards` 只包含已禁用端点。
- `stats.total_nodes` 包含已禁用端点；`stats.dynamic_nodes`、`stats.static_nodes`、`stats.online_nodes` 只统计启用端点。
- 标签筛选可以同时作用于启用端点区和已禁用端点区；前端不得把禁用端点混入启用端点列表。
- 配置概览额外返回 `topology`，用于驱动配置头部异常态展示。
- 前端可以做本页临时筛选和排序，但不得自己拼接业务视图模型。

## 节点管理

### `GET /api/v1/configs/{config_id}/nodes`

- 用途：获取配置下节点列表

### `POST /api/v1/configs/{config_id}/nodes`

- 用途：创建节点
- 请求：
  - `name`
  - `enabled`
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
- `pre_up`、`post_up`、`pre_down`、`post_down`：多条 `wg-quick` / `awg-quick` hook 命令，新建端点页面不展示，端点高级配置页维护。
- `awg_jc`、`awg_jmin`、`awg_jmax`、`awg_i1`-`awg_i5`：AmneziaWG 2.0 节点本地参数，仅所属配置为 `amneziawg_2` 时参与配置生成；新建端点时由后端随机补齐 J 参数和 I1-I5 CPS 签名链。

说明：

- `ipv4_address` 表示公网 IPv4 入口，可填写 IP 或域名。
- `ipv6_address` 表示公网 IPv6 入口，可填写 IP 或域名。
- 前端不得把二者合并成单个“公网端点”字段。
- 如果创建节点时未传 `auto_sync`，后端使用所属配置的 `auto_sync` 作为默认值。节点创建后，自动同步开关只受节点自己的 `auto_sync` 控制。
- `enabled=false` 表示端点进入可恢复软删除态。禁用端点仍保留数据，仍计入节点总数，但不参与动态/静态/在线统计、配置生成、同步、下载、远程控制和 MQTT 授权。

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
- 节点设置中的 `enabled` 通过同一次 `PUT /api/v1/nodes/{node_id}` 保存。端点从启用切换为禁用时，后端必须停用该端点相关的所有 Mesh 对。
- 禁用端点不会重置已绑定客户端；后端必须保留 `client_initialized`、MQTT 身份和客户端基础信息。重新启用时，后端不自动恢复历史 Mesh 对，也不要求客户端重新初始化，用户可以在启用端点侧手动启用或删除 Mesh 对。
- 当公网入口或监听端口变化导致相关 auto Endpoint 重算时，后端会同步清空已失效的 `persistent_keepalive`。
- 当 `virtual_ip` 变更时，后端不会自动改写 `allowed_ips`，只会返回提示，由用户手工确认。
- `POST /api/v1/nodes/awg/random` 返回一组节点级 AWG 随机参数，供端点高级配置页复用。返回值包含 `Jc/Jmin/Jmax` 和非空 `I1-I5`，其中 `I1-I5` 使用 DNS-like、STUN-like 或 QUIC-like CPS 模板生成。

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
  - `readonly`：当前节点禁用时为 `true`，前端只允许查看，不允许新建、编辑、启停或删除
  - `peer_disabled`：对端节点禁用时为 `true`
- 前端不得自行从两条 peer link 拼接 Mesh 连接卡片。

说明补充：

- 当一组 Mesh 双向连接在需要 Endpoint 的情况下两侧都无法解析公网入口时，后端会把该连接标记为 `broken`。
- 当当前启用端点的已启用 Mesh 连接指向禁用对端时，后端同样把当前连接卡片标记为 `broken`，用于给具体链路显示错误。
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
- 当前节点或对端节点已禁用时，后端返回 `NODE_DISABLED`。

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
- 创建连接时当前节点和对端节点都必须启用；否则返回 `NODE_DISABLED`。

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
- 说明：
  - 如果当前操作发生在禁用端点的 Mesh 页面，前端不得调用该接口。
  - 后端不因为对端禁用而阻止启用已有 Mesh 对；这种情况由拓扑校验报告“启用的 Mesh 连接引用不存在或已禁用端点”。

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
  - 启用的 Mesh 连接引用不存在或已禁用端点会进入 `errors`
  - 配置存在节点但还没有任何 Peer 连接会进入 `warnings`
- 那些已经在正常写入链路中被后端业务函数拦住的情况，不再重复由拓扑校验兜底。
- 启用连接引用禁用端点时，`invalid_node_ids` 只返回仍启用且需要用户处理的端点；禁用端点本身不显示 Mesh 异常标签。

同步约束：

- 只要 `mesh/validate` 返回 `valid=false`，该配置下所有节点的系统态到同步态同步都必须视为阻塞状态。

### `POST /api/v1/configs/{config_id}/mesh/quick-generate`

- 用途：按固定拓扑删除并重建当前配置下所有 Mesh 对
- 请求体：
  - `mode`：`hub_spoke`、`full_mesh` 或 `free_mesh`
  - `endpoint_ref_family`：`ipv4` 或 `ipv6`
  - `hub_node_id`：网关节点式网络必填，全连接网络和 Free Mesh 忽略
  - `gateway_node_ids`：Free Mesh 必填，表示参与骨干互联的网关节点集合
  - `leaf_assignments`：Free Mesh 必填，键为叶子节点 ID，值为其挂载的网关节点 ID
  - `use_preshared_key`：是否为自动生成的 Mesh 对启用 PSK，默认 `false`
- 行为：
  - 后端必须先完成校验，再在同一事务内删除当前配置下全部 `peer_links` 并创建新的双向 Mesh 对。
  - 生成的 Mesh 对使用 `endpoint_mode=auto`，`endpoint_ref_family` 使用请求中的地址族，`endpoint_port_mode=ref_peer_listen_port`。
  - `use_preshared_key=true` 时，后端为每一组双向 Mesh 对生成一个 PSK，并写入该组正反向两条 `peer_links`。
  - 生成后必须刷新配置状态、同步态、配置概览、节点列表、相关 Mesh 工作区和系统状态。
- 网关节点式网络：
  - 配置下至少需要 2 个启用端点。
  - `hub_node_id` 必须属于当前配置且节点启用。
  - `endpoint_ref_family=ipv4` 时网关节点必须存在 `ipv4_address`。
  - `endpoint_ref_family=ipv6` 时网关节点必须存在 `ipv6_address`。
  - 所有参与生成的启用端点必须存在 `virtual_ip`，用于生成对端 `AllowedIPs`。
  - 其它启用端点不要求公网地址。
  - 网关节点到分支节点的 `AllowedIPs` 使用分支节点虚拟 IP。
  - 分支节点到网关节点的 `AllowedIPs` 使用当前配置的 `virtual_subnet`，确保分支间流量能路由到网关节点。
- 全连接网络：
  - 配置下至少需要 2 个启用端点。
  - `endpoint_ref_family=ipv4` 时所有启用端点必须存在 `ipv4_address`。
  - `endpoint_ref_family=ipv6` 时所有启用端点必须存在 `ipv6_address`。
  - 所有参与生成的启用端点必须存在 `virtual_ip`，用于生成对端 `AllowedIPs`。
- Free Mesh：
  - 配置下至少需要 2 个启用端点。
  - `gateway_node_ids` 至少包含 1 个启用端点。
  - 网关节点必须存在当前地址族对应的公网地址。
  - 叶子节点不要求公网地址；即使存在公网地址，只要被放入 `leaf_assignments`，仍按叶子节点处理。
  - 每个启用端点必须且只能属于一种角色：网关或叶子。
  - `leaf_assignments` 中的网关必须出现在 `gateway_node_ids` 中。
  - 所有参与生成的启用端点必须存在 `virtual_ip`。
  - 网关节点之间建立全连接；网关与自己下挂的叶子节点建立双向 Mesh 对。
  - 网关到网关的 `AllowedIPs` 使用对端网关的虚拟 IP 加上对端网关下挂所有叶子节点的虚拟 IP。
  - 网关到叶子节点的 `AllowedIPs` 使用叶子节点虚拟 IP。
  - 叶子节点到网关的 `AllowedIPs` 使用当前配置的 `virtual_subnet`，确保叶子节点可访问全网。
- 响应：

```json
{
  "mode": "free_mesh",
  "endpoint_ref_family": "ipv4",
  "use_preshared_key": true,
  "generated_groups": 3,
  "deleted_links": 4,
  "affected_node_ids": ["node_a", "node_b", "node_c", "node_d"],
  "message": "Mesh links regenerated"
}
```

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/wg-preview`

- 用途：预览节点隧道配置。路径保留 `wg-preview` 以兼容现有前端，内容会根据配置所属协议输出 WireGuard 或 AmneziaWG 2.0 配置。
- 约束：节点已禁用时返回 `NODE_DISABLED`。

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
- 已禁用端点不参与配置同步状态计算，单节点同步状态接口对禁用端点返回 `NODE_DISABLED`。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`

- 用途：获取服务端已应用配置
- 约束：节点已禁用时返回 `NODE_DISABLED`。

### `PUT /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`

- 用途：保存服务端已应用配置
- 约束：节点已禁用时返回 `NODE_DISABLED`。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/download-package`

- 用途：获取下载配置页所需聚合数据
- 返回内容：文件名、同步态配置文本、下载路径
- 约束：节点已禁用时返回 `NODE_DISABLED`。

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/download-token`

- 用途：生成当前配置当前节点专用的临时下载令牌
- 鉴权：必须携带后台会话 Bearer Token
- 返回内容：
  - `access_token`
  - `token_type=download`
  - `expires_at`
  - `download_path`
  - `filename`
- 约束：节点已禁用时返回 `NODE_DISABLED`。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/download-conf?download_token=...`

- 用途：直接下载当前节点 `.conf` 文件
- 鉴权：只接受下载专用令牌
- 约束：下载令牌必须匹配当前 `config_id` 和 `node_id`
- 约束：节点已禁用时返回 `NODE_DISABLED`。
- 响应：`text/plain`，附带 `Content-Disposition`

## 工具下载接口

### `GET /api/v1/tools/download/client-options`

- 用途：获取客户端下载页的下载源、系统、架构和默认选择
- 鉴权：后台会话令牌
- 说明：`github_release` 先返回为不可用源；`local_build` 表示服务端本地源码构建

### `POST /api/v1/tools/download/client-artifacts/build`

- 用途：按下载源、系统和架构创建或复用客户端压缩包
- 鉴权：后台会话令牌
- 请求字段：
  - `source`：`github_release` 或 `local_build`
  - `goos`：`windows`、`linux`、`darwin`
  - `goarch`：`windows` 支持 `amd64`、`arm64`、`386`；`linux` 和 `darwin` 支持 `amd64`、`arm64`
- 响应字段：
  - `artifact_id`
  - `filename`
  - `download_path`
  - `source`
  - `goos`
  - `goarch`
  - `version`
  - `cached`
- 约束：`github_release` 当前返回不可用；`local_build` 只执行后端固定构建命令，命中缓存时不重复构建
- 说明：该接口只负责生成或复用产物，不直接返回文件内容。前端只把它作为“构建并下载”流程的中间结果使用，不展示 `filename`、`download_path`、`cached` 等产物状态；如果后续文件下载失败，不能把它当成构建失败。

### `GET /api/v1/tools/download/client-artifacts/{artifact_id}`

- 用途：下载客户端压缩包
- 鉴权：后台会话令牌，或绑定 `kind=client_artifact`、`resource_id=artifact_id` 的 5 分钟下载令牌

### `GET /api/v1/tools/download/config-bulk/options?config_id=...`

- 用途：获取配置批量下载页可选配置和端点
- 鉴权：后台会话令牌
- 说明：`config_id` 为空时只返回配置列表；传入后返回该配置下可下载端点

### `POST /api/v1/tools/download/config-bulk/package`

- 用途：生成配置批量下载 zip
- 生命周期：生成新批量包前，后端会删除已有配置批量 zip，只保留最近一次生成结果
- 鉴权：后台会话令牌
- 请求字段：
  - `config_id`
  - `node_ids`
- 响应字段：
  - `package_id`
  - `filename`
  - `download_path`
  - `config_id`
  - `config_name`
  - `node_count`
- 约束：只允许下载启用端点的同步态配置；不会自动执行同步

### `GET /api/v1/tools/download/config-bulk/{package_id}`

- 用途：下载配置批量 zip
- 鉴权：后台会话令牌，或绑定 `kind=config_bulk_package`、`resource_id=package_id` 的 5 分钟下载令牌

## 端口转发工具接口

### `GET /api/v1/tools/port-forwards/configs/{config_id}`

- 用途：列出当前配置下由端口转发工具托管的规则
- 鉴权：后台会话令牌
- 响应字段：规则字段外附带 `from_node`、`to_node` 摘要，前端直接展示 From / To 端点名和虚拟 IP

### `POST /api/v1/tools/port-forwards/configs/{config_id}`

- 用途：创建一条受管端口转发规则，并刷新 To 端点配置
- 鉴权：后台会话令牌
- 请求字段：
  - `from_node_id`：服务存在端点
  - `from_port`：服务端口
  - `to_node_id`：暴露转发入口并执行生命周期命令的端点
  - `to_port`：转发入口端口
  - `to_platform`：`linux` 或 `darwin`
  - `protocol`：`tcp`、`udp` 或 `all`；`all` 表示同一受管规则同时生成 TCP 与 UDP 转发
- 约束：From 与 To 必须是当前配置下启用且带 IPv4 虚拟 IP 的不同端点；同一 To 端点的同一协议端口只允许被一条受管规则占用
- 说明：后端根据 `to_platform` 生成 To 端点的受管 `PostUp` / `PreDown` 生命周期命令。规则本身不写入普通 hook 字段，端点高级配置只读展示生成命令。

### `DELETE /api/v1/tools/port-forwards/{rule_id}`

- 用途：删除端口转发工具托管的规则，并刷新 To 端点配置
- 鉴权：后台会话令牌
- 约束：受管规则只允许通过该接口删除，端点高级配置页不能直接删除对应命令

### `PUT /api/v1/tools/port-forwards/{rule_id}/enabled`

- 用途：临时启用或关闭一条端口转发规则
- 请求字段：`enabled`
- 说明：关闭后规则仍保留并继续在工具页展示，但后端不再为目的端点生成对应受管 hook；重新启用后恢复生成

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/sync`

- 用途：同步单个节点配置
- 约束：当拓扑校验失败时，后端必须拒绝执行并返回 `TOPOLOGY_INVALID`
- 约束：节点已禁用时返回 `NODE_DISABLED`

### `POST /api/v1/configs/{config_id}/sync-all`

- 用途：同步整个配置下全部节点
- 约束：当拓扑校验失败时，后端必须拒绝执行并返回 `TOPOLOGY_INVALID`

## 端点控制与运行状态

### `GET /api/v1/configs/{config_id}/endpoint/runtime-snapshot`

- 用途：获取当前配置所有节点运行快照

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/status`

- 用途：获取单个节点运行状态
- 返回补充：
  - `client_initialized`
  - `client_presence_state`
  - `client_platform`
  - `client_version`
  - `client_hostname`
  - `client_version_label`
  - `config_state.wg_config_version_state`
  - `runtime.heartbeat_client_online`
  - `runtime.heartbeat_wg_online`
  - `runtime.detect_client_online`
  - `runtime.detect_wg_online`

说明：

- `client_initialized=false` 时，端点页面进入客户端初始化页，而不是直接展示真正控制页。
- `client_presence_state` 控制台只保留三态：
  - `在线`
  - `掉线`
  - `离线`
- `client_version_label` 由后端根据客户端绑定时上报的 `platform + client_version` 聚合，例如 `Windows v1.3.2` 或 `Linux v1.3.2`。
- `config_state.wg_config_version_state` 由后端根据当前节点下发态计算，只允许：
  - `latest`：客户端 confirmed 下发态已等于服务端 staged 同步态
  - `pending`：尚未下发，或客户端 confirmed 下发态已落后
- `runtime.wg_runtime_state` 是 WG 运行态展示真相：
  - `unknown`：未知。静态节点、未初始化动态节点、客户端离线或掉线时必须返回该值。
  - `running`：客户端明确上报当前配置对应接口正在运行。
  - `stopped`：客户端在线且明确上报当前配置对应接口未运行。
- 前端不得用 `runtime.wg_running=false` 直接显示“离线”；`wg_running` 只作为兼容布尔字段。
- 节点已禁用时返回 `NODE_DISABLED`。禁用端点不得进入端点控制页。

### `GET /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/logs`

- 用途：获取控制日志

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/control`

- 用途：发送控制命令
- `action`：
  - `start`
  - `stop`
  - `push_config`
  - `wg_show`

说明：

- `start` / `stop` 通过 `control` topic 下发，只作用于当前节点 profile 对应的隧道接口。
- `push_config` 通过 `config/push` topic 下发当前节点同步态配置。客户端 ACK 为 `applied` 后，后端更新 confirmed 下发态。
- `config/push` 是唯一的“同步态 -> 客户端下发态”通道。控制台手动下发和服务端自动同步态变更后的自动下发都必须走该通道。
- 客户端收到 `config/push` 时，如果当前 profile 的 WG 接口正在运行，必须执行 stop -> 写配置 -> start；如果未运行，只写配置。
- `wg_show` 通过 `info` topic 下发。
- `wg_show` 的 ACK 只表示命令完成；具体 `wg` / `awg` 诊断输出由客户端发布到 `event` topic，服务端写入命令行回显日志。
- 服务端每次 `config/push`、`control`、`detect`、`info` 下发都会在 payload 中携带 `tunnel_protocol`。客户端 bind profile 不保存协议，运行期以当次服务端 payload 为准，避免配置协议切换后本地状态漂移。
- 节点已禁用时返回 `NODE_DISABLED`。

### `POST /api/v1/configs/{config_id}/endpoint/probe-batch`

- 用途：批量探测动态节点

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/bind-command`

- 用途：为动态节点生成一次性客户端绑定命令
- 鉴权：必须携带后台会话 Bearer Token
- 约束：
  - 仅动态节点可生成
  - 禁用节点不可生成
  - 默认有效期 5 分钟
  - 只能成功使用一次
  - 节点转为静态节点后必须立即失效
- 响应：
  - `command`
  - `expires_at`

### `POST /api/v1/configs/{config_id}/nodes/{node_id}/reset-client`

- 用途：重置当前节点客户端初始化状态
- 鉴权：必须携带后台会话 Bearer Token
- 效果：
  - MQTT 服务启用时，通过 EMQX 管理 API 删除该节点当前 MQTT 凭据；EMQX 返回 404 视为已删除
  - MQTT 服务启用时，通过 EMQX Clients API 踢出 `wfm-{node_id}` 当前连接；EMQX 返回 404 视为客户端已不在线
  - 删除或失效该节点绑定权限
  - 清空客户端运行态
  - 将 `client_initialized` 重置为 `false`
  - 控制台端点页面重新回到初始化页
- 约束：
  - 节点已禁用时返回 `NODE_DISABLED`
  - MQTT 服务启用且 EMQX 凭据删除失败时返回 `EMQX_USER_DELETE_FAILED`，避免旧客户端凭据仍可用于连接
  - MQTT 服务启用且 EMQX 客户端踢出失败时返回 `EMQX_CLIENT_DISCONNECT_FAILED`，避免旧连接继续保持在线

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
- 请求体：
  - `note`
  - `password`：当前管理员密码，后端校验后用于派生本次快照加密密钥。
- 说明：
  - 后端会先登记快照元数据，再把应用级数据库数据和 WireGuard 目录写入加密载荷。
  - 快照外层只保留 `snapshot_manifest.json` 和加密载荷 `snapshot_payload.bin`。
  - manifest 保存快照 id、创建时间、备注、快照格式版本、系统版本和解密参数。
  - 数据库内除管理员密码哈希外的应用数据全部进入快照，包括 MCP Token、MCP 审计、系统设置和客户端凭据。
  - 部署环境变量不属于数据库应用数据，不进入快照。

### `GET /api/v1/backups/list`

- 用途：获取快照列表
- 说明：
  - 列表由后端扫描 `data/backups/` 并重建索引后返回。
  - 恢复快照后，快照记录不会再因为数据库回滚到旧状态而丢失。

### `GET /api/v1/backups/download/{snapshot_id}`

- 用途：下载快照
- 鉴权：后台会话令牌，或绑定 `kind=snapshot_export`、`resource_id=snapshot_id` 的 5 分钟下载令牌

### `GET /api/v1/backups/export/{snapshot_id}`

- 用途：导出快照
- 鉴权：后台会话令牌，或绑定 `kind=snapshot_export`、`resource_id=snapshot_id` 的 5 分钟下载令牌
- 说明：与 `download/{snapshot_id}` 等价，前端统一使用导出语义。MCP 只允许导出已有快照并返回短期下载 URL，不允许创建、导入、恢复或删除快照。

### `POST /api/v1/backups/upload`

- 用途：导入快照包

### `POST /api/v1/backups/import`

- 用途：导入快照包
- 说明：
  - 只导入到快照列表，不自动恢复。
  - 导入时会校验加密快照外层结构，要求包含 manifest 与加密载荷。

### `POST /api/v1/backups/restore/{snapshot_id}`

- 用途：恢复快照
- 请求体：
  - `password`：该快照创建时使用的加密密码。
- 说明：
  - 恢复前会清空现有数据库表数据，并删除 `data/wireguard` 下全部数据。
  - 恢复后后端会重新扫描快照目录并重建 `backups` 表索引。
  - 恢复后后端必须重新执行数据库初始化，补齐当前 schema 所需默认数据。
  - 当前部署管理员密码保留，不从快照覆盖；其它数据库应用数据按快照覆盖。
  - 恢复后不信任快照中的历史在线状态，所有端点运行态先重置为离线等待重新确认。
  - 恢复后后端会用快照中的客户端 MQTT 凭据重建 EMQX 节点用户，然后主动发起一次 detect 探测，再发布全量实时状态。
  - 返回 `message` 和 `recovery`，其中 `recovery` 包含 `mqtt_credentials`、`mqtt_users_synced`、`mqtt_users_failed`。

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
  - `sync.issue_count`
  - `sync.issues`

说明：

- `system/status` 除了系统健康，还承担全局业务异常摘要。
- 已停用的配置不会再进入系统层拓扑异常统计；这类异常只保留在配置内部查看。
- 待同步统计已移除。关闭自动同步的端点属于用户主动手动维护，不进入系统异常。
- `sync.issues` 只列出启用配置下、启用且 `auto_sync=true`、但同步态未能更新到系统态的端点，供系统状态页提示人工修复。
- 左下角系统状态入口和系统状态页都直接消费这里返回的拓扑异常与自动同步异常聚合，不在前端二次计算。

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

- SSE 事件在输出前必须经过和 REST 响应一致的 JSON 编码，确保 `datetime` 等对象被序列化为可传输值，不能因为单个 payload 不可 JSON 序列化而断开整条实时流。
- 建立连接后后端应立即推送一次系统状态快照和一次 `system.clock.sync`
- 连接存活期间后端低频推送 `system.clock.sync`
- `system.clock.sync` 同时承担系统时间校时和连接活性信号，不再每秒推流
- 无在线订阅者时，服务端不做空推送
- 系统状态页删除手动刷新按钮，以 SSE 推送和前端本地走秒为准

## 当前实现边界

- Go 客户端已提供 `wfmctl + wfm-agent` 骨架，覆盖绑定、profile、MQTT 会话、心跳、事件、命令 ACK 和跨平台服务管理接口。
- 客户端不再使用注册文件；首次绑定使用 `/api/client/v1/bind` 和一次性绑定命令。
- 真正的 WireGuard 服务启停和系统级配置应用仍由客户端后续接入现有服务管理接口。

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
- 绑定 token 只能成功使用一次，bind 成功后立即失效
- bind 成功后，对应节点需要被标记为 `client_initialized=true`

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

## MCP 与 AI 接入

### `GET /api/v1/mcp-access/tokens`

- 鉴权：管理员会话
- 说明：列出 AI 接入页可查看和复制的 MCP Token。

### `POST /api/v1/mcp-access/tokens`

- 鉴权：管理员会话
- 请求体：
  - `name`
  - `permission`：`read` 或 `write`
  - `expires_at`：带时区的过期时间
- 说明：创建 MCP Token。Token 明文按产品约定保存到数据库，后续仍可在 AI 接入页复制。

### `POST /api/v1/mcp-access/tokens/{token_id}/revoke`

- 鉴权：管理员会话
- 说明：吊销 Token；已吊销 Token 不可继续访问 MCP。

### `GET /api/v1/mcp-access/audit`

- 鉴权：管理员会话
- 说明：列出 MCP Resource / Tool 调用审计。

### `/mcp`

- 协议：MCP Streamable HTTP
- 鉴权：`Authorization: Bearer <mcp-token>`
- 说明：
  - `/mcp` 和 `/mcp/` 都会进入同一个 MCP 协议入口。
  - 与控制台共用正式 Host / Origin 访问边界。
  - `read` Token 可读取首批系统状态、配置、节点、Mesh、端点、端口转发和快照元数据能力。
  - `write` Token 访问写工具时仍必须完成 MCP 标准 elicitation 交互确认；客户端不支持确认或用户拒绝时，写动作不执行。

### MCP Resource

MCP Resource 用于给 AI 客户端提供系统上下文、工具目录和常见调用示例。Resource 本身也会进入 MCP 调用审计。

- `wfm://help/overview`
  - 作用：说明 WG Free Mesh MCP 的用途、入口、Token 认证方式、read/write 权限和写入确认规则。
  - 推荐：AI 客户端首次接入或不确定能力边界时先读取。
- `wfm://help/tool-index`
  - 作用：按业务场景汇总所有 MCP tools，包括系统、配置、节点、Mesh、端点控制、同步、下载、端口转发和快照。
  - 推荐：AI 需要把用户意图映射到具体工具时读取。
- `wfm://help/workflows`
  - 作用：提供常见工作流示例，例如系统巡检、端点离线诊断、快速组网、端口转发、备份恢复。
  - 推荐：AI 执行多步任务前读取，避免跳过必要的只读检查。
- `wfm://schema/payloads`
  - 作用：说明高频写入工具 payload 的业务语义和注意事项。
  - 推荐：AI 组装 `write_create_config`、`write_update_node`、`write_quick_generate_mesh`、`write_create_port_forward_rule` 等 payload 前读取。
- `wfm://system/status`
  - 作用：读取系统状态资源，等价于 MCP 资源形式的系统状态。
- `wfm://configs`
  - 作用：读取配置列表资源。

### MCP Tool 分组

MCP tools 保持稳定命名：只读能力统一以 `read_` 开头，写入能力统一以 `write_` 开头。写入工具必须同时满足：

- MCP Token 权限为 `write`
- MCP 客户端支持 elicitation 交互确认
- 用户在确认窗口中接受本次操作

部分工具在参数缺失时会先通过 MCP elicitation 追问补齐参数，再进入最终写入确认：

- `write_build_client_artifact`：可追问下载源、目标系统和架构。
- `write_create_config_bulk_package`：可追问配置 ID 和要打包的端点 ID 列表。
- `write_export_snapshot`：可追问要导出的快照 ID。
- 追问只用于补齐参数，不代表用户已经同意执行；真正执行前仍必须再次进行写入确认。

只读工具：

- `read_system_status`：读取系统状态、拓扑摘要、同步摘要和 MQTT 状态。
- `read_configs`：读取全部 Mesh 配置列表。
- `read_config`：读取单个配置对象。
- `read_config_overview`：读取配置页聚合投影，适合修改前获取上下文。
- `read_nodes`：读取配置下端点列表。
- `read_node_workspace`：读取端点详情工作区。
- `read_mesh_workspace`：读取某端点视角下的 Mesh 连接和校验上下文。
- `read_mesh_validation`：校验配置拓扑，不修改数据。
- `read_endpoint_status`：读取动态端点运行态、客户端态、MQTT 状态和配置态。
- `read_endpoint_logs`：读取端点控制日志。
- `read_port_forward_rules`：读取受管端口转发规则。
- `read_snapshots`：读取加密快照元数据。
- `read_sync_status`：读取配置下所有端点同步状态。
- `read_node_sync_status`：读取单端点同步状态。
- `read_wg_preview`：读取单端点生成后的 WireGuard / AmneziaWG 配置预览。
- `read_client_download_options`：读取客户端下载构建选项。

写入工具：

- `write_create_config` / `write_update_config` / `write_delete_config`：创建、修改、删除配置。
- `write_create_node` / `write_update_node` / `write_delete_node`：创建、修改、删除端点。
- `write_create_tag` / `write_apply_tag` / `write_delete_tag`：维护配置标签。
- `write_create_peer_link_group` / `write_update_peer_link_group` / `write_delete_peer_link_group`：维护双向 Mesh 对。
- `write_quick_generate_mesh`：按快速组网模式删除并重建配置下 Mesh 对，属于高影响操作。
- `write_sync_node` / `write_sync_all`：同步单端点或整个配置。
- `write_endpoint_control`：下发 `start`、`stop`、`push_config`、`wg_show` 控制命令。
- `write_probe_endpoints`：通过 MQTT 探测动态端点。
- `write_create_bind_command`：创建一次性客户端绑定命令。
- `write_reset_client`：重置动态端点客户端态并撤销 MQTT 凭据。
- `write_create_port_forward_rule` / `write_set_port_forward_rule_enabled` / `write_delete_port_forward_rule`：维护受管端口转发规则。
- `write_build_client_artifact`：生成或获取客户端压缩包，并返回绑定该客户端产物的 5 分钟下载 URL。
- `write_create_config_bulk_package`：生成配置批量下载包，并返回绑定该批量包的 5 分钟下载 URL。
- `write_export_snapshot`：为已有加密快照生成 5 分钟导出 URL。MCP 不提供快照创建、导入、恢复、删除能力，也不接收任何快照密码。

### MCP 常用调用顺序

- 系统巡检：`read_system_status` -> `read_configs`
- 修改配置前：`read_config_overview` -> `read_mesh_validation` -> 写入工具
- 端点离线诊断：`read_endpoint_status` -> `read_endpoint_logs` -> `read_node_sync_status` -> `read_wg_preview`
- 快速组网：`read_config_overview` -> `read_mesh_validation` -> `write_quick_generate_mesh` -> `read_mesh_validation`
- 创建端口转发：`read_nodes` -> `read_port_forward_rules` -> `write_create_port_forward_rule`
- 快照导出：`read_snapshots` -> `write_export_snapshot`
