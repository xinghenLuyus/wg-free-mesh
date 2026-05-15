# projections

`projections/` 负责把后端业务真相整理成前端页面直接消费的读模型。

## 当前内容

- `config_list_projection.py`
  - `ConfigListProjection`：为首页配置卡片和左侧配置列表补齐拓扑摘要字段。
- `config_overview_projection.py`
  - `ConfigOverviewProjection`：聚合配置页头、节点卡片、运行快照、同步状态和拓扑摘要。
- `system_status_projection.py`
  - `SystemStatusProjection`：聚合系统状态页与左下角系统状态所需的全局摘要。

## 约定

- Projection 只负责页面快照，不做写入。
- Projection 不直接承担实时发布，由 `events/` 层决定哪些快照需要推送。
- 新增页面级快照时，优先在这里补投影，而不是继续把大块 dict 拼装塞回仓储实现。
