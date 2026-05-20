# MQTT 消息协议设计

## 目标

本文件定义 `wfm` 客户端与服务端之间通过 MQTT 交互的消息主题、消息体、ACK 规则和在线状态投影。

当前协议覆盖客户端接入、状态链路、配置下发和隧道控制。配置所属隧道协议由服务端在每次下行命令中携带，客户端 bind profile 不保存协议字段。

客户端 MQTT 密码由服务端在 bind 时生成并写入应用数据库，用于应用级快照恢复后重建 EMQX 节点用户。快照包包含该凭据和 WireGuard 私钥，必须按敏感备份保存。恢复快照后，服务端会先清空历史运行态，再重建 EMQX 用户并主动发送 detect；端点只有重新发出 heartbeat、event 或 detect ACK 后才重新在线。

## 设计范围

当前协议先覆盖：

- 配置下发
- 控制命令
- 主动探测
- 客户端事件日志回显
- 客户端心跳

暂不覆盖：

- 真实配置文本结构
- 真实控制动作细节
- 二进制传输
- 文件分片

## topic 规则

所有 topic 固定按 `config_id + node_id` 展开。

下行 topic：

- `wfm/{config_id}/{node_id}/config/push`
- `wfm/{config_id}/{node_id}/control`
- `wfm/{config_id}/{node_id}/detect`
- `wfm/{config_id}/{node_id}/info`

上行 topic：

- `wfm/{config_id}/{node_id}/config/push/ack`
- `wfm/{config_id}/{node_id}/control/ack`
- `wfm/{config_id}/{node_id}/detect/ack`
- `wfm/{config_id}/{node_id}/info/ack`
- `wfm/{config_id}/{node_id}/event`
- `wfm/{config_id}/{node_id}/heartbeat`

约束：

- 客户端只能订阅自身节点的下行 topic。
- 客户端只能发布自身节点的上行 topic。
- 服务端作为高权限 MQTT 客户端，订阅所有上行 topic。
- 不允许引入跨节点共享通配 topic 作为客户端主通道。
- EMQX HTTP AuthZ 必须按具体节点精确 topic 判断，不给客户端授权 `wfm/#`、`wfm/+` 等通配 topic。

## 统一消息 envelope

所有 MQTT 消息建议统一使用 JSON，基础 envelope 如下：

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

- `type`
  - 消息类型，例如 `event`、`heartbeat`、`ack`
- `request_id`
  - 命令型消息必须携带
  - 非命令型消息为空字符串即可
- `config_id`
  - 当前节点所属配置
- `node_id`
  - 当前节点
- `boot_id`
  - agent 进程本次启动唯一标识
- `session_id`
  - 当前 profile worker 的 MQTT 会话唯一标识
- `sent_at`
  - UTC 时间戳
- `payload`
  - 具体业务内容

## 消息类型

### 1. `config/push`

用途：

- 服务端向客户端推送当前节点同步态配置
- 这是“同步态 -> 客户端下发态”的唯一确认链路
- 如果当前 profile 的 WireGuard 接口正在运行，客户端必须先停止该接口，再写入新配置，最后重新启动该接口，使下发配置立即生效。
- 如果当前 profile 的 WireGuard 接口未运行，客户端只写入新配置，不主动启动接口。
- 服务端自动同步态变更触发的下发，和控制台“下发配置”按钮必须走同一个 `config/push` 逻辑。

下行 topic：

- `wfm/{config_id}/{node_id}/config/push`

对应 ACK：

- `wfm/{config_id}/{node_id}/config/push/ack`

下行 payload 至少包含：

```json
{
  "action": "push_config",
  "tunnel_protocol": "wireguard",
  "interface_name": "config-node",
  "config_version": 3,
  "config_sha256": "abc...",
  "config_text": "[Interface]\n..."
}
```

`tunnel_protocol` 支持：

- `wireguard`：客户端使用 `wg` 做状态检查；Linux/macOS 使用 `wg-quick` 启停隧道，Windows 使用 `wireguard.exe` tunnel service 命令。
- `amneziawg_2`：客户端使用 `awg` 做状态检查；Linux/macOS 使用 `awg-quick` 启停隧道，Windows 使用 `amneziawg.exe` tunnel service 命令。

客户端必须以本次 payload 的 `tunnel_protocol` 为准选择工具链，不得从 bind profile 缓存协议。

### 2. `control`

用途：

- 服务端控制客户端动作

下行 topic：

- `wfm/{config_id}/{node_id}/control`

当前只允许两个动作：

- `start`
- `stop`

说明：

- `start` / `stop` 只作用于当前 profile 对应的 `interface_name`。
- 客户端不得因为主机上存在其它 WireGuard 接口而把当前 profile 判定为 running。
- `control` payload 必须携带 `tunnel_protocol`，客户端按该字段选择当前平台对应工具链执行。Linux/macOS 使用 `wg-quick` / `awg-quick`，Windows 使用 `wireguard.exe` / `amneziawg.exe` 的 tunnel service 命令。

对应 ACK：

- `wfm/{config_id}/{node_id}/control/ack`

### 3. `detect`

用途：

- 服务端主动探测节点综合状态

下行 topic：

- `wfm/{config_id}/{node_id}/detect`

对应 ACK：

- `wfm/{config_id}/{node_id}/detect/ack`

说明：

- `detect` 只在前端页面有活跃用户连接时触发。
- 建议由服务端每 2 分钟触发一次。
- 没有用户查看时，不做主动探测。
- `detect` payload 携带 `tunnel_protocol`，客户端按该字段执行当前 profile 接口检测。

### 4. `info`

用途：

- 服务端按用户主动操作向客户端请求诊断信息。
- 当前用于执行裸 `wg` 或 `awg` 并通过 `event` 返回命令行回显。

下行 topic：

- `wfm/{config_id}/{node_id}/info`

对应 ACK：

- `wfm/{config_id}/{node_id}/info/ack`

说明：

- `info/ack` 只表达命令是否完成。
- 具体 stdout/stderr、命令行回显、诊断文本统一通过 `event` 上报。
- `info` payload 携带 `tunnel_protocol`，客户端按该字段执行裸 `wg` 或 `awg`，且不限定接口。

### 5. `event`

用途：

- 客户端单向事件日志回显

发布 topic：

- `wfm/{config_id}/{node_id}/event`

建议 payload：

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

语义：

- `event` 不需要 ACK。
- 服务端负责存储、展示和必要清理。
- 所有命令行输出只能放在 `event`，不能放在任何 `ack`。

### 6. `config/push ack`

用途：

- 对 `config/push` 的回执

发布 topic：

- `wfm/{config_id}/{node_id}/config/push/ack`

建议 payload：

```json
{
  "status": "accepted",
  "message": "Config received"
}
```

允许的 `status`：

- `accepted`
- `applied`
- `failed`

说明：

- `applied` 表示客户端已经完成必要的本地应用动作。
- 对运行中的接口，`applied` 必须表示 stop -> 写配置 -> start 全流程成功。
- 如果 stop、写配置或重新 start 任一步失败，必须返回 `failed`，并把底层错误放入 `message`。

### 7. `control ack`

用途：

- 对 `control` 命令的回执

发布 topic：

- `wfm/{config_id}/{node_id}/control/ack`

建议 payload：

```json
{
  "status": "accepted",
  "message": "",
  "action": "start"
}
```

允许的 `status`：

- `accepted`
- `applied`
- `failed`

### 8. `detect ack`

用途：

- 返回主动探测的综合运行信息

发布 topic：

- `wfm/{config_id}/{node_id}/detect/ack`

建议 payload：

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

说明：

- `detect ack` 是前端实时页面的主动探测状态来源。
- 服务端发出 `detect` 后，10 秒内未收到 `detect/ack`，视为探测失败。
- `detect ack` 不允许携带命令行输出。
- `client_version` 必须来自客户端构建时注入的统一版本号，服务端收到后刷新控制面板中的客户端版本字段。
- `wg_online` 只表示当前 profile 对应 `interface_name` 的运行状态，不表示主机上任意 WireGuard 接口状态。

### 9. `info ack`

用途：

- 对 `info` 命令的完成反馈。

发布 topic：

- `wfm/{config_id}/{node_id}/info/ack`

建议 payload：

```json
{
  "status": "applied",
  "action": "wg_show",
  "message": "Command completed"
}
```

说明：

- `info ack` 只更新控制日志状态。
- `wg` / `awg` 诊断输出由 `event` 承载。

### 10. `heartbeat`

用途：

- 客户端常驻心跳
- 只证明“客户端还活着”

发布 topic：

- `wfm/{config_id}/{node_id}/heartbeat`

建议 payload：

```json
{
  "client_online": true,
  "wg_online": true
}
```

语义：

- `heartbeat` 不需要 ACK。
- 客户端固定每 30 分钟发送一次。
- 服务端不只依赖 heartbeat 判断在线；heartbeat 是低频可达信号之一。
- heartbeat 是客户端单向状态上报，用于被动刷新客户端可达时间和 WireGuard 在线状态。
- `wg_online` 只表示当前 profile 对应 `interface_name` 的运行状态。

## ACK 规则

必须 ACK：

- `config/push`
- `control`
- `detect`
- `info`

不需要 ACK：

- `event`
- `heartbeat`

判定规则：

- 服务端向 broker 发布成功，不算真正成功。
- 只有收到客户端对应 `request_id` 的 ACK，才算这次动作闭环完成。
- ACK 只表达对应命令的接收、执行完成、失败或超时。
- 任意 ACK 同时证明客户端在当前时刻可达，会刷新服务端 `last_reachable_at` 和运行态在线状态。
- 命令行输出、stdout/stderr、诊断文本全部通过 `event` 上报。

## retained / LWT 规则

第一阶段建议：

- `event`
  - retained = false
- `heartbeat`
  - retained = false
- `ack`
  - retained = false

遗言建议发布到：

- `wfm/{config_id}/{node_id}/event`

LWT payload 直接表达“正常离线”事件，例如：

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

说明：

- 遗言是唯一“正常离线”的判定来源。
- 一旦收到遗言，控制台状态直接收束为 `离线`。
- 遗言之后如果又收到 heartbeat、detect ACK、control ACK、info ACK、config push ACK 或非 `offline` 的 event，说明客户端已重新可达，状态应恢复为 `在线`。

## 在线状态投影规则

控制台最终只保留三态：

- `在线`
- `掉线`
- `离线`

判定规则：

- `在线`
  - 最近存在有效可达信号，且没有更新的离线信号
- `掉线`
  - 所有有效可达信号都超过服务端 TTL
  - 或 detect 失败 / 超时导致当前可达性无法确认
- `离线`
  - 收到遗言
  - 或未初始化
  - 或已被重置
  - 或节点转静态
  - 或绑定权限已被删除

补充说明：

- 有效可达信号包括 heartbeat、detect ACK、control ACK、info ACK、config push ACK、generic ACK 和非 `offline` 的 client event。
- 服务端保留 30 分钟 heartbeat 以节约流量，在线 TTL 必须大于 heartbeat 周期；当前按 90 分钟投影，避免一次心跳丢失造成误判。
- “异常掉线”不是第四种页面状态，只是 `掉线` 的内部原因。
- 遗言是唯一正常掉线方式。
- WireGuard 展示态以 `wg_runtime_state` 为准，而不是单纯布尔值：
  - `unknown`：静态节点、未初始化动态节点、客户端离线或掉线、探测超时。
  - `running`：客户端在线并明确上报当前 profile 接口运行中。
  - `stopped`：客户端在线并明确上报当前 profile 接口未运行。
- 静态节点的 WG 状态永远是 `unknown`，不能显示“离线”。
- 裸 `wg` / `awg` 输出属于诊断信息，允许返回主机上所有 WireGuard / AmneziaWG 接口；它不参与当前 profile 的 WG 状态投影。

## 服务端高权限 MQTT 客户端职责

服务端 MQTT 客户端负责：

- 订阅所有上行 topic
- 解析 `event`
- 解析 `heartbeat`
- 解析 `config/push/ack`
- 解析 `control/ack`
- 解析 `detect/ack`
- 解析 `info/ack`
- 将结果写回数据库运行态
- 将变化推送到控制台 SSE

第一阶段不让 EMQX 规则引擎承载业务真相。

当前实现已经落地服务端高权限 MQTT 客户端：

- 启动时确保 EMQX 中存在服务端高权限 MQTT 用户。
- 订阅所有上行 topic。
- 收到 `heartbeat` 后写入客户端运行态。
- 收到 `event` 后写入客户端事件。
- `offline` event 会投影为 `离线`。
- 收到 `control/ack` 后更新控制日志。
- 收到 `info/ack` 后只更新控制日志状态。
- 收到带 `command_output` 的 `event` 后写入控制台命令行回显。
- 前端存在 SSE 订阅时，服务端每 2 分钟向启用配置中已绑定客户端的动态节点发送 `detect`。
- 通过 SSE 推送 `endpoint.status.updated` 和 `system.status.updated`。

## 客户端权限模型

控制面板下发的 `info`、`control` 命令不在服务端提权。客户端必须在本机以系统服务身份运行：

- Windows：`WfmAgent` Windows Service，账号 `LocalSystem`
- Linux：`wfm-agent.service` systemd service，第一阶段账号 `root`
- macOS：`mesh.wg-free.wfm-agent` LaunchDaemon，账号 `root`

如果客户端不是系统服务或权限不足，客户端必须通过 `event` 返回清晰错误，随后通过对应 ACK 返回 `failed`。服务端只展示真实结果，不伪造成功状态。

## 第一阶段协议验收标准

打通链路后，至少满足：

1. 客户端 bind 成功后能拿到 MQTT 凭据。
2. `wfm-agent` 能用该凭据连接 broker。
3. 服务端能持续收到 `heartbeat`。
4. 服务端能按需触发 `detect` 并收到 `detect/ack`。
5. 关闭客户端且触发遗言后，服务端能判定为 `离线`。
6. 心跳超时或探测失败后，服务端能判定为 `掉线`。
7. 服务端可以向节点 `control` topic 发布测试命令。
8. 客户端能返回对应 `control/ack`。
