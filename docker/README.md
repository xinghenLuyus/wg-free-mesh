# Docker 部署

`docker/` 用于一体化启动 WG Free Mesh 后端、前端静态资源和 EMQX。

启动后：

- 控制台访问：`http://127.0.0.1:8000`
- MQTT 明文端口：`127.0.0.1:1883`
- MQTT TLS 端口：`127.0.0.1:8883`
- EMQX Dashboard/API：默认不暴露到宿主机；需要时手动放开 `docker-compose.yml` 中的 `18083:18083`

## 目录内容

- `docker-compose.yml`：启动 `app` 和 `emqx`。
- `.env.example`：Docker 场景的环境变量模板。
- `.env`：本机实际 Docker 环境变量，不进入版本管理。
- `app/backend.Dockerfile`：后端镜像，多阶段构建前端，并在镜像内安装 Go 工具链供客户端下载页本地构建使用。
- `app/backend.Dockerfile.dockerignore`：后端镜像构建上下文排除规则。
- `emqx/`：EMQX 配置、启动脚本、证书目录和本地持久化目录。

## 首次准备

进入 Docker 目录：

```powershell
cd docker
```

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

然后打开 `docker/.env`，至少确认下面这些值：

```env
WFM_EMQX_USERNAME=admin
WFM_EMQX_PASSWORD=public
WFM_EMQX_NODE_COOKIE=wfm-emqx-cookie
WFM_EMQX_AUTHZ_SHARED_KEY=wfm-internal-emqx-authz
WFM_APP_PORT=8000
WFM_MQTT_PUBLIC_HOST=localhost
WFM_MQTT_TLS_ENABLED=false
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
```

如果是正式部署，建议修改默认密码、cookie 和共享密钥。

## 一体化启动

在 `docker/` 目录执行：

```powershell
docker compose up -d
```

首次执行会构建后端镜像，包含：

- 安装 Python 依赖。
- 构建前端并复制到镜像内。
- 安装 Go 工具链。
- 复制 `client/` 源码到镜像内，用于客户端下载页的本地源码构建。

查看运行状态：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f app
docker compose logs -f emqx
```

停止服务：

```powershell
docker compose down
```

## 访问和初始化

启动完成后访问：

```text
http://127.0.0.1:8000
```

首次打开会进入初始化页面，设置管理员密码。

EMQX Dashboard 默认不暴露到宿主机。如果需要本地访问，先取消 `docker-compose.yml` 中这一行的注释：

```yaml
- "18083:18083"
```

然后重启：

```powershell
docker compose down
docker compose up -d
```

Dashboard 地址：

```text
http://127.0.0.1:18083
```

默认账号密码来自 `docker/.env`：

```text
admin / public
```

## 数据保存位置

后端运行数据保存在项目目录：

```text
src/data -> /app/data
```

包括 SQLite 数据库、备份、WireGuard 配置、客户端下载构建产物和配置批量下载临时包。

EMQX 数据保存在本地目录：

```text
docker/emqx/data
docker/emqx/log
docker/emqx/certs
```

`docker/emqx/data` 和 `docker/emqx/log` 是运行期目录，不应作为源码内容理解。

## MQTT 和 EMQX

后端容器通过容器网络访问 EMQX，Docker 默认使用明文内部连接：

```env
WFM_MQTT_URL=mqtt://emqx:1883
WFM_EMQX_API_BASE_URL=http://emqx:18083
```

`WFM_MQTT_TLS_ENABLED` 不影响后端连接 EMQX。后端是否使用 TLS 只由 `WFM_MQTT_URL` 的 scheme 决定；Docker 默认保持 `mqtt://emqx:1883`。

客户端绑定时拿到的 MQTT 地址由这些变量控制：

```env
WFM_MQTT_PUBLIC_HOST=localhost
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
WFM_MQTT_TLS_ENABLED=false
```

`WFM_MQTT_PUBLIC_HOST` 只是客户端 MQTT 引导默认主机，不参与容器内部通信。部署到远程服务器时，应改为客户端能访问到的域名或公网 IP。

`WFM_MQTT_PUBLIC_PORT` 和 `WFM_MQTT_PUBLIC_TLS_PORT` 同时控制：

- 客户端绑定时看到的 MQTT 端口。
- Docker 映射到宿主机的 MQTT 端口。

## 应用端口

后端容器内部固定监听 `8000`。Docker 模式下可以通过 `WFM_APP_PORT` 修改宿主机映射端口：

```env
WFM_APP_PORT=8000
```

例如改为 `18000` 后，访问地址变为：

```text
http://127.0.0.1:18000
```

这个变量只影响 Docker 端口映射，不改变容器内 uvicorn 监听端口。

## 客户端 TLS 模式

默认关闭客户端 MQTT TLS：

```env
WFM_MQTT_TLS_ENABLED=false
```

需要启用客户端 TLS 时：

1. 确认 `WFM_MQTT_PUBLIC_HOST` 是客户端实际访问 EMQX 的域名或 IP。
2. 修改 `docker/.env`：

```env
WFM_MQTT_TLS_ENABLED=true
```

3. 重启：

```powershell
docker compose down
docker compose up -d
```

首次启用时，EMQX 会在 `docker/emqx/certs/` 自动生成 `ca.crt`、`server.crt` 和 `server.key`。证书已存在时不会覆盖。

启用后，EMQX 会开放 TLS listener，后端仍通过 `WFM_MQTT_URL=mqtt://emqx:1883` 连接 EMQX。客户端绑定时会拿到 `ca.crt` 内容，并在 TLS 连接时校验 CA 和 `WFM_MQTT_PUBLIC_HOST`。

如果修改了 `WFM_MQTT_PUBLIC_HOST` 并希望证书 SAN 同步更新，删除 `docker/emqx/certs/` 下旧证书后重启，EMQX 会重新生成。

## 重新构建

修改后端、前端、客户端源码或 Dockerfile 后，重新构建 app 镜像：

```powershell
docker compose build app
docker compose up -d
```

如果只改了 `docker/.env` 或 EMQX 配置，通常直接重启即可：

```powershell
docker compose down
docker compose up -d
```

## 常见排查

检查 compose 配置是否能解析：

```powershell
docker compose config
```

查看后端日志：

```powershell
docker compose logs -f app
```

查看 EMQX 日志：

```powershell
docker compose logs -f emqx
```

如果页面能打开但 MQTT 状态异常，优先检查：

- `WFM_MQTT_URL`
- `WFM_EMQX_API_BASE_URL`
- `WFM_EMQX_USERNAME`
- `WFM_EMQX_PASSWORD`
- `WFM_EMQX_AUTHZ_URL`
- `WFM_EMQX_AUTHZ_SHARED_KEY`

## 开发期只启动 EMQX

开发时如果只想启动 EMQX，本地手动运行后端和前端，可以执行 `docker compose up -d emqx`；此时 `WFM_EMQX_AUTHZ_URL` 通常保持为 `http://host.docker.internal:8000/api/internal/emqx/authz`，本地 `src/.env` 需要使用 `127.0.0.1:1883` 和 `127.0.0.1:18083`。
