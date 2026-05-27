# 目录与边界

这页用于回答“代码在哪里、职责在哪里、修改时应该碰哪一层”。它不是目录树罗列，而是维护系统时的边界说明。

## 根目录

```text
wg-free-mesh/
  src/       FastAPI 后端、数据库迁移、后端测试
  front/     Vue 控制台
  client/    Go 客户端和命令行工具
  docker/    Docker 部署入口、gateway、EMQX 配置
  docs/      VitePress 文档站点
  docs-bak/  旧文档归档，只作迁移参考
```

业务源码只应落在 `src/`、`front/`、`client/`、`docker/` 和 `docs/`。根目录不放新的业务模块，也不放临时缓存、构建产物或运行数据。

如果你还没读总体架构，先看 [总体架构](./architecture)。本页只解释目录和修改落点，不重复解释运行拓扑。

## 后端目录

```text
src/
  pyproject.toml
  alembic.ini
  migrations/
  app/
    main.py
    api/
      client/
      internal/
      v1/
    core/
    data/
    domain/
    events/
    infrastructure/
    mcp/
    projections/
    schemas/
    services/
  tests/
```

| 目录 | 边界 |
| --- | --- |
| `api/v1` | 后台 REST API。只做认证依赖、请求解析、响应包装和错误边界。 |
| `api/client` | 客户端绑定入口，面向 `wfmctl bind`，不属于控制台 API。 |
| `api/internal` | 内部系统回调，例如 EMQX AuthZ。必须依赖内部密钥，不对浏览器开放。 |
| `core` | 配置、认证、安全、公开来源限制、路径和基础异常。 |
| `data` | SQLAlchemy engine、schema、仓储、事务和数据访问组合。 |
| `domain` | 领域枚举、协议参数生成和不依赖 IO 的纯规则。 |
| `events` | SSE 事件发布和订阅管理。 |
| `infrastructure` | 外部系统适配，例如 EMQX 管理 API。 |
| `mcp` | MCP server、resources、tools、权限、确认和审计。 |
| `projections` | 面向页面的读模型聚合，例如配置概览、Mesh 工作区、系统状态。 |
| `schemas` | Pydantic 请求和响应模型。 |
| `services` | 应用用例编排，是大多数业务规则的入口。 |
| `tests` | 后端测试。临时测试数据必须进入系统临时目录或测试专用目录，不写入工作区根目录。 |

后端分层规则继续看 [后端](./backend)。接口契约继续看 [API 契约](./api-contract) 和 [API 参考](/reference/api)。

## 后端调用方向

推荐依赖方向：

```text
api -> services -> data
api -> services -> infrastructure
api -> services -> events
mcp -> services
projections -> data
services -> projections
```

不推荐的方向：

- 路由层直接写 SQL。
- 前端需要的数据由前端跨多个接口拼业务规则。
- MCP 工具绕过服务层直接改数据库。
- 仓储层调用 HTTP、EMQX、SSE 或 MCP。
- 领域层读取环境变量、数据库或网络。

## 前端目录

```text
front/
  src/
    api/
    assets/
    components/
    router/
    stores/
    types/
    views/
```

| 目录 | 边界 |
| --- | --- |
| `views` | 页面级组件，组织页面布局和页面交互。 |
| `components` | 可复用 UI 组件，不写跨资源业务规则。 |
| `router` | 路由表和路由守卫。 |
| `stores` | Pinia 状态，例如认证、布局、全局偏好。 |
| `api` | HTTP 客户端封装和接口调用函数。 |
| `types` | 前端类型定义。类型应尽量贴近后端响应，不额外发明业务字段。 |
| `assets` | 全局样式、主题变量和静态资源引用。 |

前端可以做：

- 页面布局、组件状态、加载状态和弹窗交互。
- 表单即时校验和用户输入提示。
- 调用 REST API、订阅 SSE、展示后端投影。
- 本页临时筛选、排序、折叠和搜索。

前端不应该做：

- 生成 WireGuard / AmneziaWG 配置。
- 推导节点在线、掉线、离线最终状态。
- 推导 Mesh 是否有效或哪些端点异常。
- 重新计算快速组网、AllowedIPs、Endpoint 自动摘要。
- 维护下载产物是否存在、是否命中缓存等后端内部状态。
- 绕过后端直接实现 MCP 或客户端控制业务规则。

前端页面组织、SSE 使用和 i18n 规则继续看 [前端](./frontend)。

## 客户端目录

```text
client/
  cmd/
    agent/
    ctl/
  internal/
    agent/
    bind/
    config/
    control/
    mqtt/
    profile/
    service/
```

客户端由两类程序组成：

- `wfm-agent`：系统服务，负责 MQTT 会话、配置下发、控制命令执行、状态上报和日志。
- `wfmctl`：命令行工具，负责安装、卸载、绑定、启停服务、查看状态和读取日志。

客户端不保存业务真相。它保存的是本机 profile、服务状态和最近执行结果。配置协议、AWG 参数、控制动作都应以后端当次下发 payload 为准，避免服务端配置变化后本地状态漂移。

客户端运行模型继续看 [客户端](./client)。完整 MQTT topic 和 payload 继续看 [MQTT 消息参考](/reference/mqtt-messages)。

## Docker 目录

```text
docker/
  app/
  emqx/
  gateway/
  sqlite/
  postgres/
```

| 目录 | 边界 |
| --- | --- |
| `sqlite` | SQLite 部署入口。适合个人、小规模和低维护场景。 |
| `postgres` | PostgreSQL 部署入口。适合长期运行、多数据量和更强并发需求。 |
| `app` | 应用镜像构建上下文。包含前端静态构建和后端运行环境。 |
| `gateway` | Nginx gateway 模板。统一暴露 Web/API/SSE/MCP，并可转发 MQTT 公网端口。 |
| `emqx` | EMQX 配置模板、启动脚本和证书生成逻辑。 |

Docker 是当前推荐部署方式，因为 WFM 不只是一个 Web 应用，还包含 EMQX、gateway、证书、数据库和后台协调逻辑。

部署操作继续看 [Docker 部署](/deploy/)，环境字段继续看 [环境变量参考](/reference/env)。

## 数据目录边界

运行数据默认在 `src/data`，Docker 部署会把该目录挂载到容器内应用数据目录。它包含：

- SQLite 数据库或应用数据文件。
- WireGuard / AmneziaWG 生成配置。
- 快照文件。
- 客户端构建产物。
- 配置批量下载包。

这些是运行态数据，不属于源码。文档、测试和开发脚本不能依赖里面的某个本地文件一定存在。

## 业务真相边界

数据库是唯一业务真相：

- 配置、端点、Mesh 对、端口转发、系统设置、MCP token、MCP 审计、客户端 MQTT 凭据都在数据库中。
- EMQX 是数据库状态的运行时投影。
- 客户端本地 profile 是数据库状态下发后的副本。
- SSE 是刷新信号，不是业务真相。
- 前端 store 是展示缓存，不是业务真相。

## 变更落点

常见需求的落点：

| 需求 | 首选落点 |
| --- | --- |
| 新增业务字段 | `data` schema + Alembic + repository + schema + service + docs |
| 新增页面展示字段 | 优先增加 `projections`，前端只消费投影 |
| 新增控制台接口 | `schemas` + `services` + `api/v1` + `reference/api` |
| 新增 MCP 能力 | `services` 复用 + `mcp/tools` + `mcp/resources` + MCP 文档 |
| 新增客户端命令 | `client/cmd/ctl` + `client/internal` + 客户端文档 |
| 修改 MQTT topic 或 payload | 后端 MQTT 服务 + Go 客户端 + MQTT 参考 + 客户端时序 |
| 修改数据库结构 | Alembic 迁移 + SQLAlchemy schema + 快照导入导出测试 |
| 修改 Docker 行为 | `docker/*` + 环境变量文档 + 部署文档 |

## 文档落点

- 用户如何操作：写到 `guide/` 或 `usage/`。
- 稳定字段、接口、协议、错误码：写到 `reference/`。
- 代码目录、架构边界、实现原则：写到 `developer/`。

不要把开发过程、临时方案、AI 协作记录写成用户文档。用户文档只保留当前系统真实可用的行为。

## 相关文档

- [总体架构](./architecture)
- [后端](./backend)
- [前端](./frontend)
- [客户端](./client)
- [数据库](./database)
- [协作约定](./collaboration)
