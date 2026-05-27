# 实时事件

后端通过 SSE 向前端推送系统状态和业务变更。SSE 用于刷新页面和同步局部状态，不取代 REST API。

## 入口

实时流入口：

```text
GET /api/v1/events/stream
```

请求需要管理员会话 Bearer Token。生产反向代理必须关闭响应缓冲，否则事件会延迟到达前端。

完整事件帧、事件列表和前端订阅策略见 [实时事件参考](/reference/realtime)。

如果事件由写接口触发，也要对照 [API 契约](./api-contract) 的写操作顺序。前端消费方式见 [前端](./frontend)。

## 事件原则

事件 payload 必须可 JSON 序列化。`datetime`、枚举和领域对象需要先转换为字符串或普通对象。

事件设计遵循：

- 页面能从事件知道“需要刷新什么”。
- 复杂数据仍从 API 或投影重新读取。
- 高频状态变化要控制事件量。
- 事件名保持稳定，避免前端写大量兼容分支。

## 常见事件

| 事件 | 用途 |
| --- | --- |
| `system.status.updated` | 首页、左下角系统状态和全局统计刷新。 |
| `config.list.updated` | 配置列表刷新。 |
| `config.overview.updated` | 单配置概览刷新。 |
| `node.workspace.updated` | 节点工作区刷新。 |
| `mesh.workspace.updated` | Mesh 页面刷新。 |
| `endpoint.status.updated` | 端点控制状态刷新。 |
| `control.log.created` | 新增控制日志。 |
| `control.log.updated` | 控制日志状态更新。 |
| `settings.mqtt.updated` | MQTT 设置刷新。 |
| `snapshot.list.updated` | 快照列表刷新。 |

## 前端使用方式

前端应把 SSE 事件当作刷新信号。收到事件后：

- 如果当前页面相关，重新请求对应投影。
- 如果是日志类事件，可以追加或更新局部列表。
- 如果事件与当前页面无关，可以忽略。

不要在前端根据事件 payload 重新实现后端业务推导。

## 后端发布位置

写操作完成后发布事件。常见位置：

- 配置、端点、Mesh、端口转发写操作完成后。
- 客户端 ACK 更新运行态后。
- MQTT 设置变更后。
- 快照导入、恢复、删除后。

发布事件前要确保数据库写入已经完成。

## 相关文档

- [实时事件参考](/reference/realtime)
- [前端](./frontend)
- [后端](./backend)
- [API 契约](./api-contract)
