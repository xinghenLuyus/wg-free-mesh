# events

`events/` 负责把业务变更转换成统一的 SSE 发布计划。

## 当前内容

- `publish_plan.py`
  - `PublishPlan`：描述一次业务变更后需要刷新哪些页面级快照。
- `realtime_publisher.py`
  - `RealtimePublisher`：根据发布计划调用控制平面服务，统一发出 `config.list.updated`、`config.overview.updated`、`system.status.updated` 和节点级工作区事件。

## 约定

- Router 不再手写一长串 `publish_xxx()` 调用。
- 业务层先给出影响面，再由发布器统一发送事件。
- 新增实时快照时，先扩充发布计划，再改 Router。
- SSE 事件允许丢失中间态，但不允许长期静默失真；一旦订阅者拥塞，实时层必须主动断开并让前端重连补拉当前快照。
- 运行态变化优先收束为更少的权威快照：
  - 单节点：`endpoint.status.updated`
  - 单配置：`runtime.snapshot.updated`
  - 系统摘要：`system.status.updated`
- 不再为单次运行态变化额外广播一组页面专用事件，避免同一事实被拆成多路 SSE 噪声。
