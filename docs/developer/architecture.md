# 总体架构

WG Free Mesh 由控制台、后端、数据库、Go 客户端、EMQX 和 Docker gateway 组成。开发时先确认组件边界和版本矩阵，再进入具体模块。

## 开发环境速览

版本以当前仓库配置、锁文件和 Docker 编排为准。

| 层级 | 组件 | 当前版本 / 约束 | 来源 |
| --- | --- | --- | --- |
| 应用版本 | WG Free Mesh | `1.0.0` | `src/pyproject.toml` |
| 后端运行时 | Python | `>=3.12`，Docker 镜像 `python:3.12-slim` | `src/pyproject.toml`、`docker/app/backend.Dockerfile` |
| 后端框架 | FastAPI | `>=0.115.0` | `src/pyproject.toml` |
| 后端配置 | pydantic-settings | `>=2.6.0` | `src/pyproject.toml` |
| 数据访问 | SQLAlchemy | `>=2.0.0` | `src/pyproject.toml` |
| 数据迁移 | Alembic | `>=1.13.0` | `src/pyproject.toml` |
| PostgreSQL 驱动 | psycopg | `>=3.2.0` | `src/pyproject.toml` |
| MQTT 客户端 | aiomqtt | `>=2.3.0` | `src/pyproject.toml` |
| MCP 服务 | mcp | `>=1.12.0` | `src/pyproject.toml` |
| 前端运行时 | Node.js | Docker 构建使用 `node:22-alpine` | `docker/app/backend.Dockerfile` |
| 包管理器 | pnpm | `10.33.0` | `docker/app/backend.Dockerfile` |
| 前端框架 | Vue | `3.5.32` | `front/pnpm-lock.yaml` |
| 前端构建 | Vite | `5.4.21` | `front/pnpm-lock.yaml` |
| 前端语言 | TypeScript | `5.9.3` | `front/pnpm-lock.yaml` |
| UI 组件 | Element Plus | `2.13.7` | `front/pnpm-lock.yaml` |
| 前端状态 | Pinia | `2.3.1` | `front/pnpm-lock.yaml` |
| 前端路由 | Vue Router | `4.6.4` | `front/pnpm-lock.yaml` |
| 前端 i18n | vue-i18n | `11.3.2` | `front/pnpm-lock.yaml` |
| HTTP 客户端 | Axios | `1.15.0` | `front/pnpm-lock.yaml` |
| 客户端语言 | Go | `1.22` | `client/go.mod` |
| 客户端 MQTT | paho.golang | `0.21.0` | `client/go.mod` |
| 文档站 | VitePress | `1.6.4` | `docs/package.json` |
| Gateway | Nginx | `1.27-alpine` | `docker/*/docker-compose.yml` |
| MQTT broker | EMQX | `5.8.5` | `docker/*/docker-compose.yml` |
| 生产数据库 | PostgreSQL | `16-alpine` | `docker/postgres/docker-compose.yml` |
| 本地数据库 | SQLite | Python / SQLAlchemy 内置支持 | `docker/sqlite/.env.example` |

## 组件拓扑

```text
Browser / MCP client
  -> Docker gateway (Nginx)
    -> Frontend static files (Vue / Vite)
    -> FastAPI backend
      -> Service layer
      -> SQLAlchemy repositories
      -> SQLite or PostgreSQL
      -> EMQX management API
      -> MCP server
      -> SSE event stream
    -> EMQX MQTT listeners

wfmctl
  -> Backend bind API

wfm-agent
  -> EMQX MQTT
  -> wg / awg / wg-quick / awg-quick
```

## 组件职责

### 前端控制台

前端负责页面组织、用户输入、接口调用、状态展示和交互反馈。它不复制后端业务规则，不自行判断在线状态、同步状态或下载产物状态。

### FastAPI 后端

后端是业务规则中心。配置、端点、Mesh 对、端口转发、快照、MCP、客户端绑定、MQTT 授权和系统状态都以数据库中的应用数据为准。

### 数据库

数据库是唯一业务真相。当前支持 SQLite 和 PostgreSQL，访问统一通过 SQLAlchemy。表结构变化必须进入 Alembic 迁移。

### EMQX

EMQX 只负责 MQTT 通信。节点账号、密码、授权规则和连接状态由后端根据数据库同步到 EMQX。EMQX 离线时，后端仍应能启动并落库，待 EMQX 恢复后再同步。

### Go 客户端

客户端由 `wfm-agent` 和 `wfmctl` 组成。`wfm-agent` 作为系统服务运行，接收配置和控制命令。`wfmctl` 提供安装、绑定、状态、日志、启停和卸载能力。

### Docker gateway

Docker 部署通过 gateway 提供统一 Web 入口。生产环境的 HTTPS 建议由 Nginx、Caddy 或外部网关终止，WFM 容器内部保持清晰的 HTTP 和 MQTT 边界。

## 数据流

常见写入路径：

1. 前端调用后端 API。
2. 后端校验请求并写入数据库。
3. 后端发布 SSE 事件刷新页面。
4. 如需客户端动作，后端通过 MQTT 下发命令。
5. 客户端 ACK 后，后端更新运行态和控制日志。

常见读取路径：

1. 前端请求配置、端点或系统状态。
2. 后端从数据库读取并生成投影。
3. 前端只展示投影，不重新实现业务推导。

## 控制面与数据面

WFM 管理的是 WireGuard / AmneziaWG 的配置和控制面，不转发真实隧道流量。

控制面包括：

- 浏览器访问控制台。
- 控制台调用后端 REST API。
- 控制台订阅 SSE 实时事件。
- 后端通过 EMQX 向动态客户端下发控制命令。
- 客户端通过 MQTT 上报心跳、ACK、运行状态和日志。
- MCP 客户端通过 `/mcp` 调用只读或写入工具。

数据面包括：

- 节点之间的 WireGuard / AmneziaWG UDP 隧道。
- 用户业务流量在隧道内转发。
- 端口转发规则在目标端点本机通过生命周期命令实现。

后端不代理 WireGuard 流量，也不位于 Mesh 数据路径上。后端离线后，已运行的隧道通常仍按客户端本机配置继续运行，但控制台无法继续下发新配置或控制命令。

## 运行入口

当前有三类主要入口：

| 入口 | 使用者 | 说明 |
| --- | --- | --- |
| Web/API/SSE/MCP gateway | 浏览器、AI 客户端、外部 HTTP 调用方 | Docker 部署时统一从 gateway 暴露。 |
| MQTT public listener | `wfm-agent` | 客户端连接 EMQX，端口和 TLS 由部署与设置共同决定。 |
| WireGuard / AmneziaWG UDP | 真实 Mesh 节点 | 节点之间直连，不经过 WFM 后端。 |

生产环境建议把 Web/API/SSE/MCP 放到同一个 HTTPS 反向代理入口。MQTT 可以由 gateway 暴露独立端口，是否启用 TLS 取决于客户端 MQTT 初始化设置。

## 客户端通道

动态端点上线需要两条通道：

1. 一次性 HTTP 绑定通道：`wfmctl bind` 使用绑定 token 调用 `/api/client/bind`。
2. 长期 MQTT 控制通道：`wfm-agent` 使用绑定返回的 MQTT 凭据连接 EMQX。

绑定成功后，后端把 MQTT 凭据写入数据库并同步到 EMQX。客户端本地 profile 只保存连接后端和 MQTT 所需的数据，不保存配置协议真相。每次控制、探测和配置下发时，后端都会在 payload 中携带当次协议和配置内容。

## 实时刷新通道

控制台实时刷新使用 SSE，而不是 WebSocket。设计原因：

- 控制台主要需要服务端到浏览器的刷新信号。
- 浏览器写操作已经走 REST API。
- SSE 天然支持断线重连和简单文本帧。
- 后端可以把事件视为“刷新提示”，不要求前端从事件中还原完整业务状态。

前端接收事件后按 `scope` 和事件类型重新拉取对应 REST 投影。例如配置概览变化后拉取配置概览，端点控制日志变化后拉取日志。

## EMQX 同步模型

EMQX 是运行时投影，不是业务真相。

后端负责：

- 生成节点 MQTT username/password/client_id。
- 写入数据库。
- 调用 EMQX 管理 API 创建或更新用户。
- 提供 EMQX AuthZ HTTP 回调。
- 后端启动、EMQX 恢复、快照恢复后按数据库重建 EMQX 节点账号。

EMQX 临时不可用时，后端仍应启动并允许非 MQTT 功能工作。涉及客户端控制的功能应明确报错或显示不可用，而不是让整个系统失败。

## 快照模型

快照是应用级快照，不是数据库文件拷贝。

快照包含除管理员密码外的应用数据，包括：

- 配置、端点、Mesh 对、端口转发。
- 系统设置。
- MCP token 和审计记录。
- 客户端 MQTT 凭据。
- 快照元数据和 WireGuard 目录数据。

快照恢复后，不信任历史在线态。后端会清空运行态，按快照中的客户端凭据重建 EMQX 用户，并通过 detect 重新确认端点状态。

## 失败降级

| 故障 | 期望行为 |
| --- | --- |
| EMQX 不可用 | 后端可启动；MQTT 控制不可用；数据库写入仍以数据库为准。 |
| 客户端离线 | 控制命令不能成功；页面显示离线或掉线；已有隧道状态以客户端重新上报为准。 |
| SSE 断开 | 前端自动重连；必要时重新拉取系统状态。 |
| 数据库不可用 | 后端启动失败或等待重试后失败；不能伪造业务状态。 |
| gateway 不可用 | 外部无法访问 Web/API/SSE/MCP；容器内部服务不代表公网可用。 |

## 设计取舍

- 后端优先保持可启动，不能因为 EMQX 临时不可用导致主程序不可用。
- 快照是应用级数据，不绑定 SQLite 文件或 PostgreSQL dump。
- MCP 与 Web API 共享同一套业务规则，不绕过服务层。
- Docker 是当前推荐部署方式，因为它能统一处理后端、前端、EMQX、证书和 gateway。

## 继续阅读

- 看代码目录和职责边界：[目录与边界](./project-structure)。
- 看后端服务层和仓储边界：[后端](./backend)。
- 看数据库迁移、仓储和快照关系：[数据库](./database)。
- 看动态客户端通信链路：[MQTT 协议](./mqtt-protocol) 与 [客户端接入时序](/reference/client-lifecycle)。
- 看浏览器实时刷新：[实时事件](./events) 与 [实时事件参考](/reference/realtime)。
- 看部署入口、环境变量和 HTTPS 反代：[Docker 部署](/deploy/)、[环境变量](/deploy/environment)、[反向代理](/deploy/reverse-proxy)。
