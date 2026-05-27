# MQTT 消息

本页定义服务端与 `wfm-agent` 之间的 MQTT topic、消息 envelope、消息类型、ACK 规则和在线状态投影。

MQTT 只负责低流量控制通道：配置下发、控制命令、主动探测、客户端信息、心跳和回执。数据库仍然是业务真相来源，EMQX 只是通信执行层。

## 启用与关闭

`WFM_ENABLE_MQTT_SERVICES=false` 时，系统层面禁用动态客户端能力：

- 客户端绑定不可用。
- 端点控制不可用。
- 动态端点相关 MQTT 接口返回 `MQTT_DISABLED`。
- 前端应隐藏或禁用端点控制入口。
- 后端不应依赖 EMQX 启动。

启用 MQTT 时，Docker 通过 `COMPOSE_PROFILES=mqtt` 启动 EMQX。后端会在 EMQX 在线后同步账号、授权和客户端状态。

## 连接边界

后端连接 broker 使用 `WFM_MQTT_URL`，默认是 Docker 网络内明文地址：

```text
mqtt://emqx:1883
```

客户端是否使用 TLS 由部署和绑定配置决定。`WFM_MQTT_TLS_ENABLED=true` 会开启客户端 TLS listener，并让绑定配置默认使用 TLS 端口。它不强制后端连接 EMQX 使用 TLS。

如果部署者显式把 `WFM_MQTT_URL` 配成 `mqtts://`，后端会按该地址尝试 TLS。

## 客户端绑定配置

客户端执行 `wfmctl bind` 后，通过后端 bind API 获取本地 profile。返回内容包含：

- `config_id`
- `node_id`
- `server_url`
- `mqtt.host`
- `mqtt.port`
- `mqtt.tls`
- `mqtt.username`
- `mqtt.password`
- `mqtt.client_id`
- `topics`
- TLS CA 证书，若 `tls=true`

配置所属隧道协议不保存在 bind profile 里。每次控制命令、配置下发和检测都由服务端在下行 payload 中携带 `tunnel_protocol`，客户端必须以本次消息为准选择 `wg` / `awg` 工具链。

## Topic 规则

所有 topic 都按 `config_id + node_id` 展开。

下行 topic：

| Topic | 方向 | 说明 |
| --- | --- | --- |
| `wfm/{config_id}/{node_id}/config/push` | 服务端 -> 客户端 | 下发当前节点配置。 |
| `wfm/{config_id}/{node_id}/control` | 服务端 -> 客户端 | 控制启动、停止、下发配置、查看状态。 |
| `wfm/{config_id}/{node_id}/detect` | 服务端 -> 客户端 | 主动探测客户端状态。 |
| `wfm/{config_id}/{node_id}/info` | 服务端 -> 客户端 | 请求客户端诊断信息。 |

上行 topic：

| Topic | 方向 | 说明 |
| --- | --- | --- |
| `wfm/{config_id}/{node_id}/config/push/ack` | 客户端 -> 服务端 | 配置下发回执。 |
| `wfm/{config_id}/{node_id}/control/ack` | 客户端 -> 服务端 | 控制命令回执。 |
| `wfm/{config_id}/{node_id}/detect/ack` | 客户端 -> 服务端 | 主动探测回执。 |
| `wfm/{config_id}/{node_id}/info/ack` | 客户端 -> 服务端 | 诊断命令完成回执。 |
| `wfm/{config_id}/{node_id}/event` | 客户端 -> 服务端 | 客户端事件和命令行回显。 |
| `wfm/{config_id}/{node_id}/heartbeat` | 客户端 -> 服务端 | 低频心跳。 |

约束：

- 客户端只能订阅自身节点的下行 topic。
- 客户端只能发布自身节点的上行 topic。
- 服务端作为高权限 MQTT 客户端订阅所有上行 topic。
- 不允许给客户端授权 `wfm/#`、`wfm/+` 这类通配 topic。
- EMQX HTTP AuthZ 必须按具体节点、具体 topic、具体动作判断。

## 统一 envelope

所有 MQTT 消息使用 JSON。基础 envelope：

```json
{
  "type": "heartbeat",
  "request_id": "",
  "config_id": "cfg_xxx",
  "node_id": "node_xxx",
  "boot_id": "boot_uuid",
  "session_id": "session_uuid",
  "sent_at": "2026-04-23T12:00:00Z",
  "payload": {}
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `type` | 消息类型，例如 `heartbeat`、`event`、`ack`。 |
| `request_id` | 命令型消息必须携带；非命令型消息为空字符串。 |
| `config_id` | 当前节点所属配置。 |
| `node_id` | 当前节点。 |
| `boot_id` | agent 进程本次启动唯一标识。 |
| `session_id` | 当前 profile worker 的 MQTT 会话唯一标识。 |
| `sent_at` | UTC 时间戳。 |
| `payload` | 业务内容。 |

## `config/push`

用途：

- 服务端向客户端推送当前节点的 staged 配置。
- 这是“服务端同步态 -> 客户端下发态”的确认链路。
- 控制台“下发配置”和服务端自动下发都走同一个逻辑。

下行 topic：

```text
wfm/{config_id}/{node_id}/config/push
```

ACK topic：

```text
wfm/{config_id}/{node_id}/config/push/ack
```

payload 示例：

```json
{
  "action": "push_config",
  "tunnel_protocol": "wireguard",
  "interface_name": "mesh-main-node-a",
  "config_version": 3,
  "config_sha256": "abc...",
  "config_text": "[Interface]\n..."
}
```

`tunnel_protocol` 支持：

| 值 | 客户端行为 |
| --- | --- |
| `wireguard` | 状态检查使用 `wg`；Linux/macOS 使用 `wg-quick`；Windows 使用 `wireguard.exe` tunnel service 命令。 |
| `amneziawg_2` | 状态检查使用 `awg`；Linux/macOS 使用 `awg-quick`；Windows 使用 `amneziawg.exe` tunnel service 命令。 |

如果当前 profile 对应接口正在运行，客户端应停止接口、写入新配置、再重新启动接口。只有完整流程成功，才能返回 `applied`。如果接口未运行，客户端只写入配置，不主动启动。

## `control`

用途：服务端控制客户端动作。

下行 topic：

```text
wfm/{config_id}/{node_id}/control
```

ACK topic：

```text
wfm/{config_id}/{node_id}/control/ack
```

当前动作：

| action | 说明 |
| --- | --- |
| `start` | 启动当前 profile 对应接口。 |
| `stop` | 停止当前 profile 对应接口。 |
| `push_config` | 触发配置下发流程。 |
| `wg_show` | 请求客户端返回 `wg` 或 `awg` 诊断信息。 |

payload 必须携带 `tunnel_protocol` 和 `interface_name`。客户端只能操作当前 profile 对应接口，不得因为主机上存在其他 WireGuard/AmneziaWG 接口而误判当前 profile 状态。

`wg_show` 的命令行输出不放在 ACK 中，而是通过 `event` 上报。

## `detect`

用途：服务端主动探测节点综合状态。

下行 topic：

```text
wfm/{config_id}/{node_id}/detect
```

ACK topic：

```text
wfm/{config_id}/{node_id}/detect/ack
```

规则：

- 前端存在活跃 SSE 订阅时，服务端才进行主动探测。
- 推荐频率为每 2 分钟一次。
- 没有用户查看时，不做主动探测。
- `detect` payload 携带 `tunnel_protocol`，客户端按该字段检测当前 profile 接口。
- 服务端发出 `detect` 后，超时未收到 ACK 可标记为探测失败。

ACK payload 示例：

```json
{
  "status": "applied",
  "client_online": true,
  "wg_online": true,
  "platform": "windows",
  "client_version": "0.2.3",
  "message": "Detect completed"
}
```

`client_version` 必须来自客户端构建时注入的统一版本号。服务端收到后刷新控制面板中的客户端版本字段。

`wg_online` 只表示当前 profile 对应 `interface_name` 的运行状态，不代表主机上任意 WireGuard/AmneziaWG 接口。

## `info`

用途：服务端按用户操作请求客户端诊断信息。

下行 topic：

```text
wfm/{config_id}/{node_id}/info
```

ACK topic：

```text
wfm/{config_id}/{node_id}/info/ack
```

当前主要用于执行裸 `wg` 或 `awg`，并通过 `event` 返回命令行回显。

`info/ack` 只表达命令是否完成；stdout、stderr、诊断文本统一通过 `event` 上报。

## `event`

用途：客户端单向上报事件、日志和命令行回显。

上行 topic：

```text
wfm/{config_id}/{node_id}/event
```

普通事件 payload：

```json
{
  "level": "info",
  "event": "mqtt_connected",
  "message": "MQTT session established."
}
```

命令行回显 payload：

```json
{
  "level": "info",
  "event": "command_output",
  "request_id": "req_xxx",
  "action": "wg_show",
  "stream": "stdout",
  "message": "wg completed.",
  "output": "interface: wg0\n..."
}
```

规则：

- `event` 不需要 ACK。
- 服务端负责存储、展示和清理。
- 命令行输出只能放在 `event`，不能放进任何 ACK。
- 非 `offline` 的 event 可以作为客户端近期可达信号。

## ACK

必须 ACK：

- `config/push`
- `control`
- `detect`
- `info`

不需要 ACK：

- `event`
- `heartbeat`

ACK payload 通用字段：

```json
{
  "status": "applied",
  "message": "Command completed",
  "action": "start"
}
```

允许的 `status`：

| status | 说明 |
| --- | --- |
| `accepted` | 已接收，正在处理或已进入本地队列。 |
| `applied` | 已成功执行并落到本机状态。 |
| `failed` | 执行失败，`message` 应包含可读错误。 |

判定规则：

- 服务端向 broker 发布成功，不算命令成功。
- 只有收到同 `request_id` 的 ACK，才算闭环完成。
- 任意 ACK 同时证明客户端当前可达，会刷新 `last_reachable_at`。
- ACK 不承载命令行输出。

## `heartbeat`

用途：客户端低频证明“还活着”。

上行 topic：

```text
wfm/{config_id}/{node_id}/heartbeat
```

payload：

```json
{
  "client_online": true,
  "wg_online": true
}
```

规则：

- 不需要 ACK。
- 客户端固定每 30 分钟发送一次。
- 服务端不只依赖 heartbeat 判断在线。
- `wg_online` 只表示当前 profile 对应接口。

## retained 与 LWT

第一阶段建议：

| 消息 | retained |
| --- | --- |
| `event` | false |
| `heartbeat` | false |
| `ack` | false |

LWT 建议发布到：

```text
wfm/{config_id}/{node_id}/event
```

payload：

```json
{
  "type": "event",
  "config_id": "cfg_xxx",
  "node_id": "node_xxx",
  "boot_id": "",
  "session_id": "",
  "sent_at": "2026-04-23T12:10:00Z",
  "payload": {
    "level": "info",
    "event": "offline",
    "message": "Client disconnected with will message."
  }
}
```

规则：

- 遗言是明确离线信号。
- 收到遗言后控制台状态收束为 `离线`。
- 遗言之后如果又收到 heartbeat、ACK 或非 `offline` event，说明客户端重新可达，状态恢复为 `在线` 或重新进入运行态投影。

## 在线状态投影

控制台客户端状态：

| 状态 | 含义 |
| --- | --- |
| 在线 | 最近存在有效可达信号，且没有更新的离线信号。 |
| 掉线 | 可达信号超过 TTL，或主动探测失败/超时导致可达性无法确认。 |
| 离线 | 收到遗言、未初始化、被重置、节点转静态或绑定权限被删除。 |

有效可达信号包括：

- heartbeat
- detect ACK
- control ACK
- info ACK
- config push ACK
- 非 `offline` 的 event

服务端保留 30 分钟 heartbeat 是为了节约流量。在线 TTL 必须大于心跳周期，避免一次心跳丢失就误判。

WireGuard/AmneziaWG 运行态：

| 状态 | 含义 |
| --- | --- |
| `unknown` | 静态节点、未初始化动态节点、客户端离线/掉线、探测超时。 |
| `running` | 客户端在线并明确上报当前 profile 接口运行中。 |
| `stopped` | 客户端在线并明确上报当前 profile 接口未运行。 |

裸 `wg` / `awg` 输出只用于诊断展示，不参与当前 profile 的运行态投影。

## 服务端 MQTT 客户端职责

服务端高权限 MQTT 客户端负责：

- 确保 EMQX 中存在服务端高权限用户。
- 订阅所有上行 topic。
- 解析 heartbeat、event 和各类 ACK。
- 将结果写回数据库运行态。
- 将变化通过 SSE 推送到控制台。
- 前端存在 SSE 订阅时，周期性向已绑定动态节点发送 detect。

第一阶段不让 EMQX 规则引擎承载业务真相。

## 客户端权限模型

控制命令不在服务端提权。客户端必须以系统服务身份运行：

| 平台 | 服务身份 |
| --- | --- |
| Windows | `WfmAgent` Windows Service，`LocalSystem`。 |
| Linux | `wfm-agent.service` systemd service，root。 |
| macOS | `mesh.wg-free.wfm-agent` LaunchDaemon，root。 |

如果客户端不是系统服务或权限不足，客户端必须通过 `event` 返回清晰错误，并通过对应 ACK 返回 `failed`。

## EMQX 授权

EMQX 通过内部接口回调后端：

```http
POST /api/internal/emqx/authz
x-wfm-internal-key: <WFM_EMQX_AUTHZ_SHARED_KEY>
```

允许：

```json
{ "result": "allow" }
```

拒绝：

```json
{ "result": "deny" }
```

端点重置客户端时，后端会清除客户端状态，删除或禁用 EMQX 用户，并尝试断开对应 MQTT client。
