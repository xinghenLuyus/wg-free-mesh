# 应用更新

更新前建议先在系统设置里导出快照。快照是应用级数据，可以用于 SQLite 和 PostgreSQL 之间迁移。

进入当前使用的部署目录：

```bash
cd docker/sqlite
# 或 cd docker/postgres
```

拉取最新容器并重新启动：

```bash
docker compose pull
docker compose up -d
```

Compose 会按 `.env` 中的 `WFM_IMAGE_TAG` 拉取对应版本；未设置时使用 `latest`。
