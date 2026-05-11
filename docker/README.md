# docker

`docker/` 当前同时兼容两种模式：

- 一体化启动 `app + emqx`
- 开发期只拉起 `emqx`，本地 `uvicorn` 跑后端
- MQTT 使用独立 EMQX 容器
- `wfm` 通过 EMQX 管理 API 管理节点专属 MQTT 账号
- EMQX 通过 HTTP Authorization 回查 `wfm` 的 ACL 判断
- EMQX 启动脚本按 `WFM_MQTT_TLS_ENABLED` 切换 plain / TLS 配置
- FastAPI 后端与前端开发服务器继续在本机手动启动

## 环境变量

`docker compose` 只读取 [docker/.env](D:/wenjian/stepsave/project/wg-free-mesh/docker/.env)。

- `docker/.env`：只给 compose 和容器使用
- `docker/.env` 在容器场景下应包含 `app` 运行所需的完整环境变量集合
- `src/.env`：只给本地手动运行的 FastAPI 后端使用，且其中字段必须都能在 `docker/.env` 中找到对应项

初始化时先复制：

```powershell
cd docker
Copy-Item .env.example .env
```

这样像 `WFM_EMQX_AUTHZ_URL` 这类和容器网络强相关的配置，只会留在 `docker/.env`，不会污染本地 dev 后端环境。  
约束上，`docker/.env` 是完整注入源，`src/.env` 是它的本地 dev 运行子集。
正式部署时，`docker/.env` 会统一注入 `app` 与 `emqx`；即使 `src/.env` 也存在，容器仍以 `docker/.env` 为准。

## 启动

一体化启动：

```powershell
cd docker
docker compose up -d
```

开发期只起 EMQX：

```powershell
cd docker
docker compose up -d emqx
```

访问：

- 应用: `http://127.0.0.1:8000`
- MQTT: `mqtt://127.0.0.1:1883`
- MQTT TLS: `mqtts://127.0.0.1:8883`
- EMQX Dashboard/API: `http://127.0.0.1:18083`

默认 EMQX 统一账号密码：

- `admin / public`

这组账号密码由 `WFM_EMQX_USERNAME` / `WFM_EMQX_PASSWORD` 控制，并同时用于：

- EMQX Dashboard 初始登录
- EMQX REST 管理 API bootstrap key / secret
- `wfm` 服务端 MQTT 超级用户

## TLS 开关

Docker Compose 使用 `docker/.env` 中的以下环境变量控制 EMQX 的启动模式：

```env
WFM_EMQX_NODE_COOKIE=wfm-emqx-cookie
WFM_EMQX_USERNAME=admin
WFM_EMQX_PASSWORD=public
WFM_MQTT_TLS_ENABLED=false
WFM_EMQX_AUTHZ_SHARED_KEY=wfm-internal-emqx-authz
WFM_EMQX_AUTHZ_URL=http://host.docker.internal:8000/api/internal/emqx/authz
```

说明：

- `false`：客户端使用 `1883`
- `true`：客户端使用 `8883`
- `WFM_EMQX_NODE_COOKIE`：显式覆盖 EMQX 默认 Erlang cookie，避免启动时出现 insecure cookie 警告
- Docker 中 EMQX 通过启动脚本在 plain / TLS 两套配置之间切换，避免证书缺失时 TLS listener 直接把容器启动拖死
- plain 模式下会显式关闭默认 `ssl` / `wss` listener，避免 EMQX 因默认自带证书路径缺失而启动失败
- 证书目录位于 [docker/emqx/certs](D:/wenjian/stepsave/project/wg-free-mesh/docker/emqx/certs)
- `WFM_MQTT_TLS_ENABLED=true` 但证书缺失时，EMQX 会直接拒绝启动

## 本地开发

本地开发建议按下面顺序启动：

1. 准备 `docker/.env`：

```powershell
cd docker
Copy-Item .env.example .env
```

2. 先起 EMQX：

```powershell
cd docker
docker compose up -d emqx
```

3. 再准备本地后端的 `src/.env`。

建议本地 `src/.env` 至少包含：

```env
WFM_ENABLE_MQTT_SERVICES=true
WFM_MQTT_URL=mqtt://127.0.0.1:1883
WFM_EMQX_API_BASE_URL=http://127.0.0.1:18083
WFM_EMQX_USERNAME=admin
WFM_EMQX_PASSWORD=public
WFM_EMQX_AUTHZ_SHARED_KEY=wfm-internal-emqx-authz
```

4. 再起后端：

后端：

```powershell
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 1
```

如果本地后端从 `src/` 目录启动，并使用下载工具生成客户端或配置批量下载产物，应追加 `--reload-exclude data`，避免 `src/data/artifacts/` 写入触发开发服务重载。

推荐命令：

```powershell
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-exclude data --timeout-graceful-shutdown 1
```

5. 最后起前端：

```powershell
cd front
pnpm run dev
```

说明：

- EMQX 容器回查本机 dev 后端时默认访问 `http://host.docker.internal:8000/api/internal/emqx/authz`
- Windows 和 macOS Docker Desktop 可直接使用 `host.docker.internal`
- Linux 如需兼容，compose 中已追加 `extra_hosts: host.docker.internal:host-gateway`
