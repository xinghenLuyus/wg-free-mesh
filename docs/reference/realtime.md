# 实时事件

后台控制台使用 SSE 接收实时事件。工作方式是“首屏 REST 快照 + 后续 SSE 刷新信号”，前端不通过 SSE 自行重建业务真相。

## 入口

```http
GET /api/v1/events/stream
Authorization: Bearer <access-token>
```

响应：

```http
Content-Type: text/event-stream
```

生产反向代理需要关闭响应缓冲，例如 Nginx 的 `proxy_buffering off`。否则事件可能不会实时到达浏览器。

## 帧格式

标准 SSE 帧：

```text
event: system.status.updated
id: evt_xxx
data: {"type":"system.status.updated","payload":{}}
```

字段：

| 字段 | 说明 |
| --- | --- |
| `event` | 事件类型。 |
| `id` | 事件 ID。 |
| `data` | JSON 字符串，包含事件类型和 payload。 |

`data` 必须可 JSON 序列化。`datetime`、枚举、领域对象要先转换为字符串或普通对象，不能让 SSE 因序列化失败断流。

## 连接策略

- 前端维护一个共享 SSE 连接。
- 页面进入后先请求 REST 快照，再监听 SSE。
- 页面退出时只移除监听器，不随意关闭全局连接。
- SSE 断开后由统一重连器处理。
- 后端 shutdown 时主动结束订阅，避免进程退出被浏览器连接阻塞。

无在线订阅者时，服务端不应持续生成无意义推送。

## 初始事件

连接建立后，服务端立即发送：

- `system.status.updated`
- `system.clock.sync`

连接存活期间，服务端低频发送 `system.clock.sync`，当前按 15 秒左右校准一次。前端收到后用本地定时器走秒，下次收到新事件再校准。

## 事件列表

| 事件 | 用途 | 典型 payload |
| --- | --- | --- |
| `config.list.updated` | 首页配置卡片和左侧配置列表刷新。 | `configs` |
| `config.overview.updated` | 配置概览页刷新配置头、节点卡片和标签。 | `config_id`、`overview`、`tags` |
| `node.workspace.updated` | 节点公共头和工作区刷新。 | `config_id`、`node_id`、`workspace` |
| `node.apply.updated` | 配置预览页刷新系统态、同步态和配置文本。 | `config_id`、`node_id`、`sync_status`、`preview`、`applied` |
| `mesh.workspace.updated` | Mesh 网络页刷新连接工作区。 | `config_id`、`node_id`、`workspace`、`nodes` |
| `endpoint.status.updated` | 端点控制页刷新运行态和同步态。 | `config_id`、`node_id`、`status` |
| `control.log.created` | 新增控制日志。 | `config_id`、`node_id`、`log` |
| `control.log.updated` | 控制日志状态变化。 | `config_id`、`node_id`、`log` |
| `settings.mqtt.updated` | 设置页 MQTT 表单跨页面同步。 | `mqtt` |
| `snapshot.list.updated` | 设置页快照列表刷新。 | `snapshots` |
| `system.status.updated` | 首页、系统状态页、左下角全局状态刷新。 | `summary`、`services`、`sync`、`topology` |
| `system.clock.sync` | 服务端时间校准和 SSE 活性信号。 | `timestamp` |

## Mesh 工作区刷新

Mesh 相关字段变化会影响多个节点。比如某个节点的公网地址、监听端口或 Mesh 对变化时，后端不仅要刷新当前节点，也要刷新受影响 peer 节点的 `mesh.workspace.updated`。

`workspace.connections[*]` 应带上连接完整性结果，前端直接展示断裂标签，不自行判断拓扑。

## 端点控制刷新

`endpoint.status.updated` 的触发来源：

- heartbeat 被动上报。
- detect 主动探测 ACK 或超时。
- info/control/config push ACK。
- 客户端 event。
- 重置客户端。

`info/ack`、`control/ack` 只更新控制日志状态。命令行回显来自 MQTT `event`，后端写入日志后再发 `control.log.created`。

## 前端使用约定

前端收到事件后：

- 当前页面相关：重新请求对应投影。
- 日志类事件：追加或更新日志行。
- 系统状态事件：更新全局状态和左下角状态。
- 不相关事件：忽略。

不要在前端根据事件 payload 重新实现在线、同步、拓扑或产物状态推导。

## 后端发布约定

写入数据库后再发布事件。常见发布点：

- 配置、端点、标签写操作完成后。
- Mesh 连接新建、修改、删除、启停后。
- 端口转发规则创建、启停、删除后。
- 同步状态变化后。
- 客户端运行状态变化后。
- 控制日志新增或更新后。
- MQTT 设置变化后。
- 快照创建、导入、恢复、删除后。

Mesh 连接变化除了刷新当前页面，也要刷新配置列表和系统状态，使首页统计保持一致。
