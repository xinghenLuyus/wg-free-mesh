# data

`data/` 是后端数据库基础设施与仓储层。

## 当前内容

- `connection.py`
  - 创建 SQLAlchemy Engine。
  - 提供仓储层使用的 `connect()` 兼容执行入口。
  - 支持 SQLite 与 PostgreSQL。
- `schema.py`
  - 统一维护 SQLAlchemy 表结构元数据。
  - Alembic 和启动初始化共用这份 metadata。
- `database.py`
  - 初始化运行目录。
  - 启动时协调 Alembic 迁移到最新 schema。
  - 全新数据库会创建当前 schema 并标记为最新迁移；已有数据库会按现有字段推断迁移点后继续升级。
  - 执行启动时必要的数据修正。
- `application_snapshot.py`
  - 导出应用级数据库快照。
  - 恢复应用级快照。
  - 快照包含动态客户端 MQTT 凭据，用于恢复后重建 EMQX 节点用户。
- `paths.py`
  - 运行数据目录、备份目录、WireGuard 目录定位。
- `store.py`
  - 业务服务统一依赖的仓储入口。
- `repositories/`
  - 按业务能力拆分仓储 mixin、行映射和命名规则。

## 约定

- 业务服务只依赖 `app.data.store.store`，不直接依赖具体数据库。
- 数据库结构只在 `schema.py` 和 Alembic migration 中维护。
- 备份包使用应用级 `database.json`，不直接复制数据库物理文件。
- `infrastructure/database.py` 只保留兼容 re-export，不再承载数据库实现。
