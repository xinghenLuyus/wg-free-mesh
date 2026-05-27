# Docker 部署

WG Free Mesh 目前只推荐 Docker 部署。

这个系统不是一个单进程 Web 应用。它包含控制台、后端 API、数据库、EMQX、MQTT 授权、客户端 TLS 证书、下载产物、快照导入导出和统一入口。Docker 部署会把这些组件放进固定的网络和目录结构里，并自动处理大量 EMQX 相关实现，减少手动配置出错的概率。

生产环境建议先阅读 [环境变量](/deploy/environment)，改完必要变量后再启动。公网访问建议再阅读 [反向代理](/deploy/reverse-proxy)，用 HTTPS 暴露控制台和 API。

## 选择数据库

SQLite 和 PostgreSQL 使用同一套应用逻辑，快照也按应用级数据导出，方便在两种数据库之间迁移。

| 方案 | 适合场景 | 特点 |
| --- | --- | --- |
| SQLite | 本机、轻量部署、单人管理、小规模节点 | 文件型数据库，部署简单，备份直观，资源占用低。 |
| PostgreSQL | 长期运行、多人使用、更高并发、生产环境 | 独立数据库服务，连接池和并发能力更稳，适合后续扩展。 |

如果只是先跑起来，选 SQLite。如果准备长期对外提供服务，选 PostgreSQL。

## 启动前检查

启动前至少确认这些事：

- 已复制 `.env.example` 为 `.env`。
- 已修改生产环境必须修改的密码和密钥。
- `WFM_PUBLIC_ORIGIN` 已改成真实访问地址，例如 `https://wfm.example.com`。
- 如果不需要客户端远程控制和 MQTT，已关闭 `WFM_ENABLE_MQTT_SERVICES` 并清空 `COMPOSE_PROFILES`。
- 如果需要从公网访问，已准备反向代理和 HTTPS。

完整说明见 [环境变量](/deploy/environment)。

## SQLite 启动

SQLite 目录适合最小化部署。数据会挂载到项目的 `src/data`，方便本机查看、备份和迁移。

```bash
cd docker/sqlite
cp .env.example .env
```

编辑 `.env` 后启动：

```bash
docker compose up -d
```

默认访问：

```text
http://localhost:8000
```

## PostgreSQL 启动

PostgreSQL 目录会额外启动数据库容器。生产环境更推荐这个方案。

```bash
cd docker/postgres
cp .env.example .env
```

编辑 `.env`，至少修改 PostgreSQL 密码、EMQX 密码和共享密钥，然后启动：

```bash
docker compose up -d
```

默认访问：

```text
http://localhost:8000
```

## 启动后

第一次打开控制台后，按页面提示完成管理员初始化。随后可以创建配置、添加端点、下载客户端并绑定节点。

如果启用了 MQTT，EMQX 可能比后端更晚就绪。短时间内看到等待 EMQX 或等待端点上线属于正常现象；后端会在 EMQX 在线后同步账号、授权和客户端连接信息。

## 更新

更新代码后，在对应目录重新构建并启动：

```bash
docker compose up -d --build
```

更新前建议先在系统设置里导出快照。快照是应用级数据，可以用于 SQLite 和 PostgreSQL 之间迁移。
