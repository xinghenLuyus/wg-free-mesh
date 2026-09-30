# Docker 部署

WG Free Mesh 目前只推荐 Docker 部署。

这个系统不是一个单进程 Web 应用。它包含控制台、后端 API、数据库、EMQX、MQTT 授权、客户端 TLS 证书、下载产物、快照导入导出和统一入口。Docker 部署会把这些组件放进固定的网络和目录结构里，并自动处理大量 EMQX 相关实现，减少手动配置出错的概率。

生产环境建议先阅读 [环境变量](/deploy/environment)，改完必要变量后再启动。公网访问建议再阅读 [反向代理](/deploy/reverse-proxy)，用 HTTPS 暴露控制台和 API。

## 获取代码

先克隆项目代码，并进入项目目录：

```bash
git clone https://github.com/xinghenLuyus/wg-free-mesh.git
cd wg-free-mesh
```

## 选择数据库

SQLite 和 PostgreSQL 使用同一套应用逻辑，快照也按应用级数据导出，方便在两种数据库之间迁移。

| 方案 | 适合场景 | 特点 |
| --- | --- | --- |
| SQLite | 本机、轻量部署、单人管理、小规模节点 | 数据直接保存在项目的 src/data 目录中，方便查看、备份和迁移。 |
| PostgreSQL | 长期运行、多人使用、更高并发、生产环境 | 额外启动 PostgreSQL 数据库容器，更适合长期运行或生产环境。 |

## SQLite 启动

进入 SQLite 部署目录：

```bash
cd docker/sqlite
```

复制环境变量配置文件：

```bash
cp .env.example .env
```

然后编辑 .env。

至少确认以下配置：

- 修改生产环境中需要使用的密码和密钥。

- 将 WFM_PUBLIC_ORIGIN 修改为实际访问地址。

例如：

```text
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

如果只需要 Web 控制台，不需要客户端远程控制或 MQTT 服务，可以关闭：

```text
WFM_ENABLE_MQTT_SERVICES=false
COMPOSE_PROFILES=
```

完整说明见 [环境变量](/deploy/environment)。

配置完成后启动：

```bash
docker compose up -d
```

默认访问：

```text
http://localhost:8000
```

## PostgreSQL 启动

进入 PostgreSQL 部署目录，并复制环境变量配置文件：

```bash
cd docker/postgres
cp .env.example .env
```

编辑 `.env`，至少修改：

- PostgreSQL 数据库密码

- EMQX 密码

- 共享密钥

- WFM_PUBLIC_ORIGIN

例如：

```text
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

如果只需要 Web 控制台，不需要客户端远程控制或 MQTT 服务，可以关闭：

```text
WFM_ENABLE_MQTT_SERVICES=false
COMPOSE_PROFILES=
```

完整说明见 [环境变量](/deploy/environment)。

配置完成后启动：

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

## 镜像版本

Docker 部署默认使用 `latest` 镜像。`latest` 指向项目当前公开推荐版本；如果当前还没有正式版本，它会指向最新的 RC 版本。

一般部署不需要关心镜像版本，直接执行：

```bash
docker compose up -d
```

如果你需要生产环境固定版本、避免自动跟随 `latest`，可以在 `.env` 中指定镜像标签，例如：

```env
WFM_IMAGE_TAG=1.0.0
```

预发布版本也可以固定，例如：

```env
WFM_IMAGE_TAG=1.0.0-rc.1
```
