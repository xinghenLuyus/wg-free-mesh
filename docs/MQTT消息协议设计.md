# MQTT 消息协议设计

## 目标

本文件定义 `wfm` 客户端与服务端之间通过 MQTT 交互的消息主题、消息体、ACK 规则和在线状态投影。

当前先固化“客户端接入与状态链路”阶段的协议，不展开具体 WireGuard 业务字段。

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

上行 topic：

- `wfm/{config_id}/{node_id}/config/push/ack`
- `wfm/{config_id}/{node_id}/control/ack`
- `wfm/{config_id}/{node_id}/detect/ack`
- `wfm/{config_id}/{node_id}/event`
- `wfm/{config_id}/{node_id}/heartbeat`

约束：

- 客户端只能订阅自身节点的下行 topic。
- 客户端只能发布自身节点的上行 topic。
- 服务端作为高权限 MQTT 客户端，订阅所有上行 topic。
- 不允许引入跨节点共享通配 topic 作为客户端主通道。

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

- 服务端向客户端推送最新配置

下行 topic：

- `wfm/{config_id}/{node_id}/config/push`

对应 ACK：

- `wfm/{config_id}/{node_id}/config/push/ack`

### 2. `control`

用途：

- 服务端控制客户端动作

下行 topic：

- `wfm/{config_id}/{node_id}/control`

当前只允许两个动作：

- `start`
- `stop`

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
- 建议由服务端每分钟触发一次。
- 没有用户查看时，不做主动探测。

### 4. `event`

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

语义：

- `event` 不需要 ACK。
- 服务端负责存储、展示和必要清理。

### 5. `config/push ack`

用途：

- 对 `config/push` 的回执

发布 topic：

- `wfm/{config_id}/{node_id}/config/push/ack`

建议 payload：

```json
{
  "status": "accepted",
  "message": "",
  "config_version": 12
}
```

允许的 `status`：

- `accepted`
- `applied`
- `failed`

### 6. `control ack`

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

### 7. `detect ack`

用途：

- 返回主动探测的综合运行信息

发布 topic：

- `wfm/{config_id}/{node_id}/detect/ack`

建议 payload：

```json
{
  "status": "applied",
  "agent_state": "running",
  "mqtt_state": "connected",
  "wireguard_state": "running",
  "last_error": ""
}
```

说明：

- `detect ack` 是前端实时页面的主要综合状态来源。
- 服务端发出 `detect` 后，10 秒内未收到 `detect/ack`，视为探测失败。

### 8. `heartbeat`

用途：

- 客户端常驻心跳
- 只证明“客户端还活着”

发布 topic：

- `wfm/{config_id}/{node_id}/heartbeat`

建议 payload：

```json
{}
```

语义：

- `heartbeat` 不需要 ACK。
- 客户端固定每 30 分钟发送一次。
- 服务端超过 45 分钟未收到 heartbeat，视为心跳超时。

## ACK 规则

必须 ACK：

- `config/push`
- `control`
- `detect`

不需要 ACK：

- `event`
- `heartbeat`

判定规则：

- 服务端向 broker 发布成功，不算真正成功。
- 只有收到客户端对应 `request_id` 的 ACK，才算这次动作闭环完成。

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

## 在线状态投影规则

控制台最终只保留三态：

- `在线`
- `掉线`
- `离线`

判定规则：

- `在线`
  - 最近 heartbeat 未超时
  - 且最近一次 detect 成功
- `掉线`
  - heartbeat 超时
  - 或 detect 失败
  - 或 detect 返回综合异常
- `离线`
  - 收到遗言
  - 或未初始化
  - 或已被重置
  - 或节点转静态
  - 或绑定权限已被删除

补充说明：

- “异常掉线”不是第四种页面状态，只是 `掉线` 的内部原因。
- 遗言是唯一正常掉线方式。

## 服务端高权限 MQTT 客户端职责

服务端 MQTT 客户端负责：

- 订阅所有上行 topic
- 解析 `event`
- 解析 `heartbeat`
- 解析 `config/push/ack`
- 解析 `control/ack`
- 解析 `detect/ack`
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
- 通过 SSE 推送 `endpoint.status.updated` 和 `system.status.updated`。

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
