# 后端

后端使用 FastAPI，负责业务 API、MCP、SSE、快照、数据库访问、EMQX 同步和客户端绑定。

开始改后端前，先确认 [目录与边界](./project-structure) 中的依赖方向。稳定 HTTP 行为以 [API 契约](./api-contract) 和 [API 参考](/reference/api) 为准。

## 目录入口

主要目录：

| 目录 | 作用 |
| --- | --- |
| `src/app/api` | HTTP API 路由，包含后台 API、客户端 API、内部 EMQX 回调。 |
| `src/app/core` | 配置、认证、安全、路径中间件等基础能力。 |
| `src/app/data` | SQLAlchemy schema、数据库连接和仓储组合。 |
| `src/app/domain` | 领域模型和协议参数生成逻辑。 |
| `src/app/events` | SSE 实时事件发布。 |
| `src/app/infrastructure` | 外部系统适配，例如 EMQX 管理 API。 |
| `src/app/mcp` | MCP server、资源、工具、权限和审计。 |
| `src/app/projections` | 页面和系统状态投影。 |
| `src/app/services` | 业务用例入口。 |
| `src/app/schemas` | Pydantic 请求和响应模型。 |

## 分层规则

路由层只处理：

- 认证和权限依赖。
- 请求模型解析。
- HTTP 状态和错误边界。
- 调用服务层。

服务层处理：

- 业务用例编排。
- 跨仓储操作。
- 发布事件。
- 调用 EMQX、下载工具、快照和 MCP 相关能力。

仓储层处理：

- SQL 读写。
- 数据结构转换。
- 与数据库强相关的唯一性、查询和事务边界。

投影层处理：

- 首页状态。
- 配置概览。
- 节点工作区。
- 系统状态。

前端需要复杂展示数据时，优先让后端增加投影，而不是让前端拼业务规则。

典型投影包括配置概览、Mesh 工作区、端点控制状态和系统状态。对应页面行为可以对照 [前端](./frontend)、[实时事件](./events) 和 [数据模型](/reference/data-model)。

## 状态原则

数据库是唯一真相。运行态、客户端状态、MQTT 凭据、端口转发规则、MCP token 和系统设置都应以数据库记录为准。

EMQX 是外部执行层。后端在 EMQX 在线时同步账号和授权，离线时先落库，恢复后统一同步。

涉及 MQTT 凭据、在线态或 EMQX 回调时，同时更新 [MQTT 协议](./mqtt-protocol)、[MQTT 消息参考](/reference/mqtt-messages) 和 [客户端接入时序](/reference/client-lifecycle)。

## 错误处理

业务错误使用统一错误结构，错误码要稳定。新增错误码时同步 [错误码参考](/reference/errors)。

不要把 Python 异常、数据库异常或第三方库异常直接暴露给前端。应转换为可解释的业务错误。

## 实时发布

写操作完成后，如果影响页面状态，应发布 SSE 事件。事件 payload 必须可 JSON 序列化，`datetime` 需要转换为字符串。

事件命名、payload 和前端刷新策略见 [实时事件](./events) 与 [实时事件参考](/reference/realtime)。

## 测试边界

后端测试以 `python -m pytest` 为主。测试应覆盖：

- API 行为。
- 仓储和迁移兼容。
- 快照导入导出。
- EMQX 离线和恢复同步。
- MCP 权限、确认和审计。

## 相关文档

- [目录与边界](./project-structure)
- [API 契约](./api-contract)
- [数据库](./database)
- [实时事件](./events)
- [MQTT 协议](./mqtt-protocol)
- [MCP 参考](/reference/mcp)
