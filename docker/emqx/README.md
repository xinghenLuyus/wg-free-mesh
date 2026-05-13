# emqx

`docker/emqx/` 保存 `wfm` 开发期本地集成用的 EMQX 配置。

## 当前内容

- `base.hocon`
  - EMQX 基础配置
  - 启用内建数据库认证
  - 启用 HTTP Authorization 回查 `wfm`
- `base.tls.hocon`
  - EMQX TLS 配置
  - 在 plain 配置基础上额外打开 8883 TLS listener
- `start-emqx.sh`
  - 按 `WFM_MQTT_TLS_ENABLED` 在两套配置之间切换
  - TLS 开启且证书缺失时，根据 `WFM_MQTT_PUBLIC_HOST` 自动生成 CA 和服务端证书
  - 启动前写入 `WFM_EMQX_AUTHZ_URL` 与 `WFM_EMQX_AUTHZ_SHARED_KEY`
  - 启动前生成 `wfm-api-keys.conf`，将统一账号密码写成 EMQX REST API bootstrap key
- `certs/`
  - TLS 证书目录
- `data/`
  - EMQX 持久化数据目录
- `log/`
  - EMQX 日志目录

## 说明

- 这些配置由 [docker/.env](D:/wenjian/stepsave/project/wg-free-mesh/docker/.env) 驱动，不读取 `src/.env`。
- 本地开发时，`docker/.env` 负责容器侧回查地址与 TLS 开关，`src/.env` 负责本机后端连接 EMQX 管理 API 的参数。
- `WFM_EMQX_NODE_COOKIE` 会通过环境变量注入 EMQX，避免使用默认不安全 Erlang cookie。
- `WFM_EMQX_USERNAME` / `WFM_EMQX_PASSWORD` 是唯一需要维护的 EMQX 账号密码，同时用于 Dashboard、管理 API 与服务端 MQTT 超级用户。
- plain 模式下会显式关闭默认 `ssl` / `wss` listener；TLS 模式只开启我们需要的 `8883`。

- 默认 HTTP Authorization 回查：
  - `http://host.docker.internal:8000/api/internal/emqx/authz`
- 回查请求会附带：
  - `x-wfm-internal-key: ${WFM_EMQX_AUTHZ_SHARED_KEY}`
- 当前 Docker 方案里，EMQX 账号由 `wfm` 服务端通过管理 API 创建和更新。
- `WFM_MQTT_TLS_ENABLED=false` 时，客户端仍走 1883。
- `WFM_MQTT_TLS_ENABLED=true` 时，客户端走 8883；如果 `certs/` 下证书缺失，启动脚本会自动生成。

## 目录约定

- `certs/` 由 EMQX 启动脚本维护，TLS 模式下至少包含：
  - `ca.crt`
  - `server.crt`
  - `server.key`
- 证书已存在时不会覆盖；修改 `WFM_MQTT_PUBLIC_HOST` 后如需更新证书 SAN，删除旧证书并重启 EMQX。
- `data/` 与 `log/` 仅用于容器本地持久化，不参与版本管理。
