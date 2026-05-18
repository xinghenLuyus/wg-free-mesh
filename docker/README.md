# Docker 启动

`docker/` 下按数据库类型提供两套启动目录：

- `sqlite/`：轻量部署，应用数据挂载到项目 `src/data/`。
- `postgres/`：使用 PostgreSQL，适合长期运行。

两套启动方式都会启动：

- `app`：后端服务，并托管前端静态资源。
- `emqx`：客户端 MQTT broker。

Compose 项目名按数据库类型区分：

- SQLite：`wg-free-mesh-sqlite`
- PostgreSQL：`wg-free-mesh-postgres`

两套环境可以避免互相识别 orphan 容器。由于 EMQX 默认占用相同宿主机端口，通常不要同时启动两套完整环境。

默认访问地址：

- 控制台：`http://127.0.0.1:8000`
- MQTT 明文端口：`127.0.0.1:1883`
- MQTT TLS 端口：`127.0.0.1:8883`

## SQLite

```bash
cd docker/sqlite
cp .env.example .env
docker compose up -d --build
```

## PostgreSQL

```bash
cd docker/postgres
cp .env.example .env
docker compose up -d --build
```

PostgreSQL 数据目录为：

```text
docker/postgres/data/pgdata
```

## 常用命令

以下命令在 `docker/sqlite` 或 `docker/postgres` 目录内执行。

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f emqx
docker compose down
```

重新构建应用容器：

```bash
docker compose build app
docker compose up -d
```

## 关键注意事项

- `WFM_APP_PORT` 只控制宿主机端口映射，容器内 app 固定监听 `8000`。
- App 镜像包含 `alembic.ini` 和 `migrations/`，容器启动时会自动把 SQLite 或 PostgreSQL 数据库升级到当前 schema。
- `WFM_MQTT_PUBLIC_HOST` 是写入客户端绑定配置的主机名，远程部署时应改成客户端可访问的域名或 IP。
- `WFM_MQTT_TLS_ENABLED=true` 会启用客户端 TLS listener，并作为客户端绑定默认 TLS 开关；不影响后端连接 EMQX。
- 后端连接 EMQX 由 `WFM_MQTT_URL` 决定，默认是 Docker 网络内的 `mqtt://emqx:1883`。
- EMQX Dashboard/API 默认不暴露。如需本地管理，取消 compose 中 `18083:18083` 的注释。
- EMQX TLS 证书在缺失时自动生成到 `docker/emqx/certs/`。修改 `WFM_MQTT_PUBLIC_HOST` 后，如需更新证书 SAN，删除旧证书并重启 EMQX。
- 备份使用应用级快照，不直接复制数据库物理文件；SQLite 和 PostgreSQL 之间可以通过快照迁移。

## 开发模式

开发期只启动 EMQX，后端和前端在本机运行。开发模式统一走 `docker/sqlite`：

```bash
cd docker/sqlite
cp .env.example .env
docker compose up -d emqx
```

此时通常需要把 `docker/sqlite/.env` 中的回调地址改成本机后端：

```env
WFM_EMQX_AUTHZ_URL=http://host.docker.internal:8000/api/internal/emqx/authz
```

本机后端 `.env` 使用本机端口连接 EMQX：

```env
WFM_MQTT_URL=mqtt://127.0.0.1:1883
WFM_EMQX_API_BASE_URL=http://127.0.0.1:18083
```
