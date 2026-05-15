# Docker 部署

`docker/` 提供两套数据库启动方式：

- `sqlite/`：默认轻量部署，数据库文件保存在 `src/data/wg_free_mesh.db`。
- `postgres/`：使用 PostgreSQL，适合长期运行或多数据量场景。

两套 compose 都会启动：

- `app`：FastAPI 后端，同时托管前端静态资源。
- `emqx`：客户端 MQTT 通信 broker。

启动后默认访问：

- 控制台：`http://127.0.0.1:8000`
- MQTT 明文端口：`127.0.0.1:1883`
- MQTT TLS 端口：`127.0.0.1:8883`
- EMQX Dashboard/API：默认不暴露；需要时取消 compose 中 `18083:18083` 的注释。

## SQLite 启动

```powershell
cd docker/sqlite
Copy-Item .env.example .env
docker compose up -d --build
```

SQLite 数据通过项目相对路径挂载：

```text
src/data -> /app/data
```

备份、WireGuard 配置、客户端下载产物和配置批量下载临时包也都在这个目录下。

## PostgreSQL 启动

```powershell
cd docker/postgres
Copy-Item .env.example .env
docker compose up -d --build
```

PostgreSQL 数据保存在：

```text
docker/postgres/data/pgdata
```

compose 挂载的是 `docker/postgres/data`，容器内 `PGDATA` 指向其下的 `pgdata/` 子目录。这样可以保留源码里的空目录占位文件，同时避免 PostgreSQL 初始化时报“目录非空”。

应用启动初始化数据库时会在连接失败后短暂重试。PostgreSQL 首次初始化期间会经历临时 server 到正式 server 的切换，应用会等待正式连接可用后继续启动，超过超时时间才退出。

`WFM_DATABASE` 默认指向 compose 内部的 `postgres` 服务：

```env
WFM_DATABASE=postgresql+psycopg://wfm:wfm@postgres:5432/wfm
```

如需改数据库名、用户名或密码，同步修改：

```env
WFM_POSTGRES_DB=wfm
WFM_POSTGRES_USER=wfm
WFM_POSTGRES_PASSWORD=wfm
WFM_DATABASE=postgresql+psycopg://wfm:wfm@postgres:5432/wfm
```

## 常用命令

以下命令都在所选数据库目录内执行，例如 `docker/sqlite` 或 `docker/postgres`。

查看状态：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f app
docker compose logs -f emqx
```

停止：

```powershell
docker compose down
```

重新构建 app：

```powershell
docker compose build app
docker compose up -d
```

## 关键环境变量

应用端口：

```env
WFM_APP_PORT=8000
```

这个变量只控制宿主机端口映射，容器内 app 仍监听 `8000`。

数据库：

```env
WFM_DATABASE=sqlite:///./data/wg_free_mesh.db
```

或：

```env
WFM_DATABASE=postgresql+psycopg://wfm:wfm@postgres:5432/wfm
```

后端连接 EMQX：

```env
WFM_MQTT_URL=mqtt://emqx:1883
WFM_EMQX_API_BASE_URL=http://emqx:18083
```

客户端 MQTT 接入地址：

```env
WFM_MQTT_PUBLIC_HOST=localhost
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
WFM_MQTT_TLS_ENABLED=true
```

`WFM_MQTT_PUBLIC_HOST` 只用于客户端引导，部署到远程主机时应改为客户端能访问到的域名或 IP。`WFM_MQTT_TLS_ENABLED` 只影响客户端接入 listener 和客户端默认 TLS 引导，不影响后端连接 EMQX；后端是否使用 TLS 只由 `WFM_MQTT_URL` 的 scheme 决定。

## 客户端 TLS

启用：

```env
WFM_MQTT_TLS_ENABLED=true
```

首次启动时，EMQX 会按 `WFM_MQTT_PUBLIC_HOST` 自动生成长期自签 CA 与服务端证书，写入：

```text
docker/emqx/certs
```

证书已存在时不会覆盖。修改 `WFM_MQTT_PUBLIC_HOST` 后，如果希望证书 SAN 同步更新，删除旧证书并重启 EMQX。

## 备份迁移

备份包使用应用级快照，不直接复制数据库物理文件。也就是说，SQLite 生成的备份可以导入 PostgreSQL，PostgreSQL 生成的备份也可以导入 SQLite。

恢复备份会清空现有数据库表数据，并清空 `data/wireguard` 后再导入快照内容。

## EMQX 运行目录

以下目录只保留空目录，运行内容不进入 Git：

```text
docker/emqx/data
docker/emqx/log
docker/emqx/certs
```

## 开发期只启动 EMQX

开发时如果只想启动 EMQX，本地手动运行后端和前端，可以在所选数据库目录执行 `docker compose up -d emqx`；此时 `WFM_EMQX_AUTHZ_URL` 通常改为 `http://host.docker.internal:8000/api/internal/emqx/authz`，本地 `src/.env` 使用 `127.0.0.1:1883` 和 `127.0.0.1:18083`。
