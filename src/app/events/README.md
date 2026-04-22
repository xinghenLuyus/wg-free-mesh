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
