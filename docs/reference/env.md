# 环境变量参考

环境变量使用 `WFM_` 前缀，Docker 示例位于 `docker/sqlite/.env.example` 和 `docker/postgres/.env.example`。

## Runtime

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WFM_DEBUG` | `false` | 后端调试模式。 |
| `WFM_ENABLE_DEV_TEST_API` | `false` | 开发例外开关；开启后注册 `/api/v0` 并跳过正式来源限制。 |
| `WFM_TIMEZONE` | `Asia/Shanghai` | 控制台显示时区。 |
| `WFM_AUTH_TOKEN_EXPIRE_MINUTES` | `1440` | 管理员登录 token 有效期。 |
| `WFM_AUTH_DOWNLOAD_TOKEN_EXPIRE_MINUTES` | `5` | 下载 token 有效期。 |

## Public access / Gateway

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WFM_PUBLIC_ORIGIN` | `http://localhost:8000` | 服务主来源。生产环境建议设为 HTTPS 公网入口。 |
| `WFM_EXTRA_ALLOWED_ORIGINS` | `[]` | 额外允许来源，JSON 数组。只扩展 Origin，不扩展 Host。 |
| `WFM_APP_PORT` | `8000` | 宿主机暴露的 Gateway Web 端口。 |
| `WFM_GATEWAY_CLIENT_MAX_BODY_SIZE` | `512m` | Gateway 最大请求体，影响快照导入。 |

## Database

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `WFM_DATABASE` | `sqlite:///./data/wg_free_mesh.db` | SQLAlchemy 数据库连接字符串。 |
| `WFM_POSTGRES_DB` | `wfm` | PostgreSQL 容器初始化数据库。 |
| `WFM_POSTGRES_USER` | `wfm` | PostgreSQL 用户。 |
| `WFM_POSTGRES_PASSWORD` | `wfm` | PostgreSQL 密码。 |
| `WFM_POSTGRES_PORT` | `5432` | 宿主机暴露 PostgreSQL 端口。 |

## MQTT / EMQX

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WFM_ENABLE_MQTT_SERVICES` | `true` | 是否启用客户端绑定、MQTT 通信和远程控制。 |
| `COMPOSE_PROFILES` | `mqtt` | Docker Compose 是否启动 EMQX profile。关闭 MQTT 时留空。 |
| `WFM_MQTT_URL` | `mqtt://emqx:1883` | 后端连接 broker 的内部地址。 |
| `WFM_MQTT_PUBLIC_PORT` | `1883` | 客户端明文 MQTT 接入端口。 |
| `WFM_MQTT_PUBLIC_TLS_PORT` | `8883` | 客户端 TLS MQTT 接入端口。 |
| `WFM_MQTT_TLS_ENABLED` | `true` | 是否启用客户端 MQTT TLS listener。 |
| `WFM_EMQX_API_BASE_URL` | `http://emqx:18083` | 后端访问 EMQX 管理 API 的内部地址。 |
| `WFM_EMQX_USERNAME` | `admin` | EMQX Dashboard、管理 API 和服务端 MQTT 超级用户。 |
| `WFM_EMQX_PASSWORD` | `public` | EMQX 密码，生产环境必须修改。 |
| `WFM_EMQX_NODE_COOKIE` | `wfm-emqx-cookie` | EMQX 节点 cookie。 |
| `WFM_EMQX_AUTHZ_SHARED_KEY` | `wfm-internal-emqx-authz` | EMQX HTTP AuthZ 回查共享密钥，生产环境必须修改。 |
| `WFM_EMQX_AUTHZ_URL` | `http://app:8000/api/internal/emqx/authz` | EMQX 回调后端做 topic 授权的内部地址。 |
