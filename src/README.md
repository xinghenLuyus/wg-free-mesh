# src

`src/` 是本项目的 FastAPI 后端工程。

## 当前范围

- 认证与会话
- 配置管理
- 节点管理
- Peer Link / Mesh 校验
- WireGuard 配置预览
- 系统态与同步态管理
- 端点运行态、控制日志、批量 probe
- SSE 实时事件
- MQTT 公网引导参数设置
- EMQX 节点级账号与 HTTP 授权回查
- 备份恢复
- 系统状态聚合
- 工具下载，包含客户端本地源码构建和配置批量下载
- 客户端绑定、MQTT 账号授权、心跳、事件、命令 ACK 和重置客户端

## 认证初始化

后端不会写入默认管理员密码。首次启动后，如果数据库没有有效 `admin` 密码哈希，前端会进入 `/setup` 设置初始密码。

认证使用 Bearer Token：

- `POST /api/v1/auth/setup` 设置初始密码并返回 token。
- `POST /api/v1/auth/login` 登录并返回 token。
- 业务接口需要 `Authorization: Bearer <token>`。
- 修改密码会轮换 token secret，使旧 token 失效。

## Mesh Endpoint 规则

- `ipv4_address` 是公网 IPv4 入口，可填写 IP 或域名。
- `ipv6_address` 是公网 IPv6 入口，可填写 IP 或域名。
- `endpoint_ref_family` 只使用 `ipv4` 或 `ipv6`。
- `endpoint_mode=auto` 为尽力生成：对向对应公网入口存在则写 Endpoint，不存在则留空。
- `endpoint_mode=none` 强制不写 Endpoint。
- `endpoint_mode=manual` 必须填写 Host 和 Port。
- WireGuard Endpoint 只有在 Host 是 IPv6 字面量时才加方括号，域名不加。

可配置项：

```powershell
WFM_DEBUG=true
WFM_CORS_ORIGINS=["http://localhost:5173","http://localhost:8080"]
WFM_DATABASE=sqlite:///./data/wg_free_mesh.db
WFM_AUTH_TOKEN_EXPIRE_MINUTES=1440
WFM_ENABLE_MQTT_SERVICES=true
WFM_MQTT_URL=mqtt://127.0.0.1:1883
WFM_MQTT_PUBLIC_HOST=localhost
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
WFM_MQTT_TLS_ENABLED=false
WFM_EMQX_API_BASE_URL=http://127.0.0.1:18083
WFM_EMQX_USERNAME=admin
WFM_EMQX_PASSWORD=public
WFM_EMQX_AUTHZ_SHARED_KEY=wfm-internal-emqx-authz
WFM_TIMEZONE=Asia/Shanghai
WFM_ENABLE_DEV_TEST_API=false
```

环境变量示例文件放在 [`.env.example`](D:/wenjian/stepsave/project/wg-free-mesh/src/.env.example)，实际本地配置文件应放到 `src/.env`。后端配置不会再从项目根目录读取 `.env`。
`src/.env` 只负责本地 dev 后端启动所需配置；其中需要的字段必须都能在 [docker/.env](D:/wenjian/stepsave/project/wg-free-mesh/docker/.env) 中找到对应项。  
`docker/.env` 是容器 / 生产场景的完整环境变量注入源；在 Docker 场景下，`app` 与 `emqx` 都以它为准。  
也就是说：`src/.env` 应是 `docker/.env` 的可运行子集，而不是另一套并行配置体系。
时间存储仍统一使用 UTC，控制台默认显示时区由 `WFM_TIMEZONE` 控制，默认值为北京时间 `Asia/Shanghai`。
`WFM_ENABLE_DEV_TEST_API` 默认关闭；只有显式设为 `true` 时，`/api/v0` 开发测试接口才会注册。

数据库连接由 `WFM_DATABASE` 控制，默认 `sqlite:///./data/wg_free_mesh.db`。Docker SQLite 与 PostgreSQL 启动目录分别提供自己的 `.env.example`，本地开发通常继续使用 SQLite。  
客户端对外可见的 MQTT 默认 `host`、`port` 与 `tls` 来自 `WFM_MQTT_PUBLIC_HOST`、`WFM_MQTT_PUBLIC_PORT`、`WFM_MQTT_PUBLIC_TLS_PORT` 和 `WFM_MQTT_TLS_ENABLED`，前端设置页可以覆盖保存给后续绑定使用；客户端 MQTT 能力是否启用只由 `WFM_ENABLE_MQTT_SERVICES` 这个部署环境变量控制，不暴露给前端设置页。EMQX 容器侧的 TLS listener、证书路径、回查地址等容器专用参数由 `docker/.env` 控制。  
`WFM_MQTT_PUBLIC_HOST` 只是客户端 MQTT 引导默认主机，可以填写服务主机的域名或 IP，不参与后端连接 EMQX 的内部通信。  
TLS 开启时，后端从项目相对路径 `docker/emqx/certs/ca.crt` 读取 CA，并在客户端绑定时下发给客户端；客户端会校验 CA 和 MQTT 主机名。Docker 模式下该目录以只读方式挂载到 app 容器。  
`WFM_APP_PORT` 只用于 Docker Compose 宿主机端口映射，后端本地运行不读取该变量。  
EMQX 统一账号密码为 `WFM_EMQX_USERNAME` / `WFM_EMQX_PASSWORD`，本地手动运行后端且修改过 Docker 默认值时，需要让本地后端读取到同一组值。  
`WFM_ENABLE_MQTT_SERVICES=false` 时，后端不会启动 MQTT 入口服务，所有客户端绑定和远程控制能力都会被禁用。

## 手动运行

安装依赖：

```powershell
cd src
python -m pip install -e .[dev]
```

开发启动后端：

```powershell
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 1
```

说明：

- 当前项目包含 SSE 长连接。
- `fastapi dev` / `fastapi run` 不支持 `--timeout-graceful-shutdown` 参数。
- 为避免浏览器仍然保持连接时拖住后端退出，开发启动命令统一使用 `uvicorn`，并增加 `--timeout-graceful-shutdown 1` 作为停机兜底。
- 如果本地后端从 `src/` 目录启动，下载工具会在 `src/data/artifacts/` 写入客户端和批量配置产物；使用 `--reload` 时应追加 `--reload-exclude data`，避免产物写入触发开发服务重载。

推荐开发启动命令：

```powershell
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-exclude data --timeout-graceful-shutdown 1
```


可访问：

- OpenAPI: `http://127.0.0.1:8000/docs`
- 健康检查: `http://127.0.0.1:8000/api/v1/system/health`
- SSE: `http://127.0.0.1:8000/api/v1/events/stream`
- 开发测试重置接口: `http://127.0.0.1:8000/api/v0/dev/reset-bootstrap`

SSE 需要附带 Bearer Token：

```http
GET /api/v1/events/stream HTTP/1.1
Authorization: Bearer <access_token>
```

`/api/v1/events/stream` 会记录连接 ID、客户端地址、用户和连接存活时长，便于定位移动端长连接问题。

开发测试重置接口不要求后台 token，可直接命令行调用：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v0/dev/reset-bootstrap
```

该接口只清初始化态相关设置：

- 管理员密码哈希
- 登录 token secret
- 密码更新时间
- `ui_locale`
- `ui_theme_mode`

不会删除配置、节点、Mesh 关系和业务快照。

## 测试

```powershell
cd src
python -m pytest -q
```

## 生产说明

- 生产态由 FastAPI 同时提供 API 和前端静态资源
- FastAPI 优先读取根目录 `front/dist`
- Docker 镜像会先构建前端，再把 `dist` 复制进后端镜像
- Docker 模式将项目目录 `src/data` 挂载到容器内 `/app/data`，和本地后端开发使用同一份运行数据
- 数据层使用 SQLAlchemy，迁移目录为 `src/migrations/`，数据库入口为 `WFM_DATABASE`
- 备份恢复使用应用级快照，可在不同数据库之间导入恢复
- 生产启动命令同样带 `--timeout-graceful-shutdown 1`，避免 SSE 长连接阻塞停机
- 下载工具生成的客户端构建产物缓存到后端运行数据目录 `data/artifacts/clients/`；配置批量下载临时包写入 `data/artifacts/config-bulk/`，每次生成新包时会删除旧包，只保留最近一次生成结果。本地开发使用 `--reload` 时应排除 `data` 目录，避免产物写入触发重载

## 目录索引

- [app/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/README.md)：应用主包入口。
- [app/api/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/README.md)：API 分层说明。
- [app/api/internal/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/internal/README.md)：内部基础设施接口。
- [app/core/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/core/README.md)：配置、安全、错误和响应。
- [app/domain/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/domain/README.md)：领域模型。
- [app/data/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/data/README.md)：数据库基础设施、仓储入口与应用级快照。
- [app/infrastructure/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/infrastructure/README.md)：基础设施兼容入口。
- [app/schemas/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/schemas/README.md)：请求与响应模型。
- [app/services/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/services/README.md)：认证、控制平面与实时服务。
- [tests/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/tests/README.md)：后端测试说明。
