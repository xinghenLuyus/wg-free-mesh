# 开发环境启动

本页只描述本地开发时最常用的三进程启动方式：Docker 启动 EMQX，本机启动 FastAPI 后端，本机启动 Vite 前端。完整 Docker 部署仍以 [Docker 部署](/deploy/) 为准。

## 版本要求

本地开发建议和仓库、Docker 构建环境保持一致：

| 组件 | 版本 / 约束 | 说明 |
| --- | --- | --- |
| Python | `>=3.12` | 后端 `src/pyproject.toml` 要求。当前开发推荐使用 conda 环境，例如 `wfm`。 |
| Node.js | `22.x` | Docker 前端构建使用 `node:22-alpine`。 |
| pnpm | `10.33.0` | Docker 构建固定使用该版本。 |
| EMQX | `5.8.5` | Docker Compose 使用 `emqx/emqx:5.8.5`。 |

依赖安装属于本机环境变更，应由维护者手动执行。自动化助手不得代替维护者安装、升级或删除依赖。

## 启动顺序

开发时按这个顺序启动：

1. 通过 Docker 启动 EMQX。
2. 通过 `uvicorn` 启动后端。
3. 通过 `pnpm run dev` 启动前端。

## 1. 启动 EMQX

推荐复用 SQLite 部署目录里的 EMQX 配置：

```bash
cd docker/sqlite
cp .env.example .env
```

修改回调地址到本机：

```dotenv
WFM_EMQX_AUTHZ_URL=http://host.docker.internal:8000/api/internal/emqx/authz
```

打开 compose 中注释的 EMQX Dashboard/API 端口 `18083`，否则 EMQX 回调功能无法正常使用。

本地开发只启动 EMQX：

```bash
docker compose up -d emqx
```

## 2. 启动后端

后端从 `src/` 目录启动，并读取 `src/.env`。

进入后端目录：

```bash
cd src
python -m pip install -e .[dev]
cp .env.example .env
```

说明：

- `WFM_ENABLE_DEV_TEST_API=true` 会注册 `/api/v0`，并放宽正式来源限制，只能用于开发。
- `WFM_EXTRA_ALLOWED_ORIGINS` 要包含 Vite 前端地址，否则浏览器从 `5173` 调后端会被来源限制拦截。
- `WFM_MQTT_URL` 是后端连接 EMQX 的地址；本机后端访问 Docker EMQX 时使用 `127.0.0.1:1883`。
- `WFM_EMQX_API_BASE_URL` 是后端访问 EMQX Dashboard/API 的地址；前提是开发时已经暴露 `18083`。
- `WFM_PUBLIC_ORIGIN` 会影响客户端下载、绑定命令和部分公开 URL 的生成。前端本地调试时通常设为后端地址。

使用 `uvicorn` 启动：

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-exclude data --timeout-graceful-shutdown 1
```

后端启动后常用地址：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/v1/system/health`
- SSE：`http://127.0.0.1:8000/api/v1/events/stream`

## 3. 启动前端

前端使用 Vite：

```bash
cd front
pnpm run dev
```

访问：

```text
http://127.0.0.1:5173
```

前端运行在 `5173` 时，默认会把 API 和 SSE 指向同主机的 `8000`，也就是：

```text
http://127.0.0.1:8000
```

如果需要显式指定后端地址，可以在前端启动前设置：

```bash
export VITE_API_BASE_URL='http://127.0.0.1:8000'
pnpm run dev
```

前端不使用 Vite proxy。开发期间跨域由后端来源配置控制。

## 常见问题

### 前端能打开，但接口被拒绝

优先检查 `src/.env`：

```dotenv
WFM_ENABLE_DEV_TEST_API=true
WFM_EXTRA_ALLOWED_ORIGINS=["http://127.0.0.1:5173","http://localhost:5173"]
```

如果从手机或其它局域网设备访问前端，还要把对应来源加入 `WFM_EXTRA_ALLOWED_ORIGINS`，并确认后端 Host 限制允许该访问方式。

### 后端显示 MQTT 或 EMQX 异常

按顺序检查：

1. EMQX 容器是否运行。
2. `1883` 是否映射到宿主机。
3. `18083` 是否在开发时临时暴露。
4. `src/.env` 和 `docker/sqlite/.env` 的 EMQX 用户名、密码、AuthZ shared key 是否一致。
5. `docker/sqlite/.env` 的 `WFM_EMQX_AUTHZ_URL` 是否指向 `http://host.docker.internal:8000/api/internal/emqx/authz`。

### 后端 reload 反复重启

确认启动命令包含：

```bash
--reload-exclude data
```

`src/data` 是本地运行数据目录，会写入数据库、下载产物、配置批量包和快照。它不应该触发后端开发重载。
