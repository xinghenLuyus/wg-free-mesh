# app

`src/app/` 是后端应用主包，负责把 API、配置、领域模型、数据层和服务组织成一个可运行的 FastAPI 工程。

## 当前文件

- `__init__.py`
  - 标记 `app` 为 Python 包，不承载业务逻辑。
- `main.py`
  - `lifespan(...)`：应用启动时初始化数据库。
  - `create_app()`：创建 FastAPI 实例、注册异常处理、中间件、`/api/internal`、`/api/v0`、`/api/v1` 与前端静态资源托管。
  - `app`：供 `uvicorn` 或 `fastapi dev` 启动的应用对象。

## 当前子模块

- `api/`：HTTP 与 SSE 路由入口。
- `core/`：配置、错误、响应、安全、基础校验。
- `data/`：SQLAlchemy 连接、schema、Alembic 配套数据层、仓储入口和应用级快照。
- `domain/`：领域模型与枚举。
- `events/`：实时事件发布计划与统一发布器。
- `infrastructure/`：数据库与文件系统基础设施。
- `projections/`：页面级读模型投影。
- `schemas/`：Pydantic 请求与响应模型。
- `services/`：认证、控制平面、拓扑、SSE 等应用服务。

## 约定

- `app/` 根目录不直接堆业务逻辑，业务行为优先下沉到 `services/` 与 `data/repositories/`。
- 页面快照聚合优先放进 `projections/`，不要继续把大段 dict 拼装堆回仓储层。
- 实时事件的影响面优先通过 `events/PublishPlan` 收束，不在 Router 中手写零散 `publish_xxx()`。
- 新增代码文件时，必须同步更新当前目录或子目录的 README，说明用途与关键入口。
