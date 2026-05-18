# MQTT 集成设计

## 目标

`wfm` 当前保留 EMQX 作为独立 broker，由后端负责节点 MQTT 账号、权限与客户端 bind 参数的统一真相。

目标是：

- Docker 按数据库目录启动，并兼容开发期只拉 EMQX
- `docker/sqlite/.env`、`docker/postgres/.env` 与 `src/.env` 职责分离
- 客户端 bind 后拿到节点专属 MQTT 凭据
- EMQX 认证和授权都能被 `wfm` 统一控制
- 客户端 TLS 开关可通过后端与 Docker 环境变量统一收口

## 总体方案

- Broker：EMQX
- AuthN：EMQX 内建账号库
- AuthZ：EMQX HTTP Authorization 回查 `wfm`
- 真相源：`wfm`

职责边界：

- `wfm`
  - 使用统一账号密码作为 EMQX 管理 API 凭据和服务端 MQTT 超级用户
  - 生成或轮换节点专属 MQTT 用户名与密码
  - 将节点专属 MQTT 密码写入应用数据库，作为应用级快照的一部分，用于恢复后重建 EMQX 节点用户
  - 调 EMQX 管理 API 创建、更新、删除账号
  - 对 EMQX 的 pub/sub 回查请求返回 allow / deny
  - 在 bind 响应中下发 MQTT 连接参数
- EMQX
  - 维护 MQTT 协议连接
  - 校验账号密码
  - 在每次 publish / subscribe 时回查 `wfm`

## Docker 落地

目录：

- [docker/sqlite/docker-compose.yml](D:/wenjian/stepsave/project/wg-free-mesh/docker/sqlite/docker-compose.yml)
- [docker/sqlite/.env.example](D:/wenjian/stepsave/project/wg-free-mesh/docker/sqlite/.env.example)
- [docker/postgres/docker-compose.yml](D:/wenjian/stepsave/project/wg-free-mesh/docker/postgres/docker-compose.yml)
- [docker/postgres/.env.example](D:/wenjian/stepsave/project/wg-free-mesh/docker/postgres/.env.example)
- [docker/emqx/base.hocon](D:/wenjian/stepsave/project/wg-free-mesh/docker/emqx/base.hocon)
- [docker/emqx/base.tls.hocon](D:/wenjian/stepsave/project/wg-free-mesh/docker/emqx/base.tls.hocon)
- [docker/emqx/start-emqx.sh](D:/wenjian/stepsave/project/wg-free-mesh/docker/emqx/start-emqx.sh)

环境变量边界：

- Docker 数据库目录内的 `.env`
  - 只给 Docker Compose 和容器使用
  - 在 Docker 场景下同时作为 `app` 与 `emqx` 的完整注入源
  - 例如 `WFM_DATABASE`、`WFM_EMQX_AUTHZ_URL`、`WFM_MQTT_TLS_ENABLED`
- `src/.env`
  - 只给本地手动运行的 FastAPI 后端使用
  - 例如 `WFM_EMQX_API_BASE_URL=http://127.0.0.1:18083`
  - 字段集合必须是 `docker/.env` 的子集

这样容器网络内的回查地址、TLS listener 开关不会和本地 dev 后端的配置混在一起。

当前规则：

- `WFM_MQTT_TLS_ENABLED=false`
  - EMQX 使用明文配置
  - 客户端默认拿到 1883
- `WFM_MQTT_TLS_ENABLED=true`
  - EMQX 启用 TLS listener
  - 客户端默认拿到 8883
  - EMQX 启动脚本会在证书缺失时根据 `WFM_MQTT_PUBLIC_HOST` 自动生成 `docker/emqx/certs/` 下的 CA 和服务端证书
- `WFM_EMQX_AUTHZ_URL`
  - 开发期默认回查本机后端 `http://host.docker.internal:8000/api/internal/emqx/authz`
- `WFM_MQTT_TLS_ENABLED`
  - 只影响客户端绑定参数和 EMQX 客户端 TLS listener，不影响后端连接 EMQX
- `WFM_MQTT_URL`
  - 后端连接 EMQX 的 broker 地址；是否使用 TLS 只由 URL scheme 决定

## 后端配置

关键环境变量：

- `WFM_ENABLE_MQTT_SERVICES`
- `WFM_EMQX_API_BASE_URL`
- `WFM_EMQX_USERNAME`
- `WFM_EMQX_PASSWORD`
- `WFM_EMQX_AUTHZ_SHARED_KEY`
- `WFM_MQTT_URL`

说明：

- `WFM_ENABLE_MQTT_SERVICES=false` 时，后端不会启动 MQTT 入口服务，客户端绑定、远程控制和 MQTT 状态检查全部禁用。
- `WFM_EMQX_USERNAME` / `WFM_EMQX_PASSWORD` 是唯一 EMQX 账号密码，同时用于 Dashboard、REST 管理 API bootstrap key 与服务端 MQTT 超级用户。
- 客户端可见的 MQTT `host / port / tls` 由前端设置页维护
- MQTT 客户端能力是否启用只由部署环境变量 `WFM_ENABLE_MQTT_SERVICES` 控制，不暴露给前端设置页
- Docker 只负责 EMQX 容器层的 TLS listener 与 AuthZ 回查地址
- `docker/.env` 负责 compose 与容器之间的连接参数
- 在 Docker 正式部署中，`docker/.env` 也负责给 `app` 注入完整运行参数
- `src/.env` 负责本地手动启动后端时连接 `127.0.0.1:18083` 这类开发参数

对应配置入口：

- [config.py](D:/wenjian/stepsave/project/wg-free-mesh/src/app/core/config.py)

## 内部接口

### `POST /api/internal/emqx/authz`

用途：

- 供 EMQX 在 publish / subscribe 时回查授权结果

请求头：

- `x-wfm-internal-key`

请求体：

```json
{
  "username": "node_xxx",
  "clientid": "wfm-node_xxx",
  "topic": "wfm/cfg_xxx/node_xxx/status",
  "action": "publish"
}
```

响应体：

```json
{
  "result": "allow"
}
```

或：

```json
{
  "result": "deny"
}
```

## 节点级隔离

当前授权规则按节点粒度隔离：

- 用户名默认使用 `node_id`
- `client_id` 默认使用 `wfm-{node_id}`
- topic 权限按 `config_id + node_id` 收口

允许订阅：

- `wfm/{config_id}/{node_id}/config/push`
- `wfm/{config_id}/{node_id}/control`
- `wfm/{config_id}/{node_id}/detect`

允许发布：

- `wfm/{config_id}/{node_id}/heartbeat`
- `wfm/{config_id}/{node_id}/config/push/ack`
- `wfm/{config_id}/{node_id}/control/ack`
- `wfm/{config_id}/{node_id}/detect/ack`
- `wfm/{config_id}/{node_id}/event`

如果节点不存在、节点不是动态节点、配置已停用、`client_id` 不匹配，授权必须直接拒绝。

## 当前落地状态

已经完成：

- Docker compose 切换到 EMQX，并兼容 `docker compose up -d` 与 `docker compose up -d emqx`
- EMQX plain / TLS 双配置切换骨架
- `EmqxService` 管理 API 封装骨架
- `MqttAuthService` 节点级 topic ACL 判断
- `/api/internal/emqx/authz` 内部回查接口
- 节点 bind 时创建或轮换 EMQX 账号
- 节点 bind 时在 TLS 模式下下发 CA 证书，客户端据此校验 EMQX 服务端证书
- 重置客户端时删除 EMQX 节点账号，并在 AuthZ 回查中校验 `client_initialized` 与登记的 MQTT 身份，避免旧凭据继续发布或订阅
- 快照恢复时清空历史在线运行态，使用快照中的 MQTT 密码重建 EMQX 节点账号，并主动触发 detect
- Go 客户端 bind 后保存本地 profile 并连接 MQTT
- 服务端作为高权限 MQTT 客户端订阅上行 topic
- MQTT 服务启停状态纳入系统检查，并由 `WFM_ENABLE_MQTT_SERVICES` 作为部署级开关统一控制客户端相关能力

配套文档：

- [MQTT消息协议设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/MQTT消息协议设计.md)
- [客户端接入时序设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端接入时序设计.md)
