# 数据库

数据库通过 SQLAlchemy 统一访问，当前支持 SQLite 和 PostgreSQL。

数据库是业务真相来源。先读 [总体架构](./architecture) 的“业务真相边界”，再看本页的迁移和仓储规则。

## 入口文件

| 文件或目录 | 作用 |
| --- | --- |
| `src/app/data/schema.py` | SQLAlchemy 表定义。 |
| `src/app/data/database.py` | engine、连接和初始化。 |
| `src/app/data/repositories` | 业务仓储 mixin。 |
| `src/migrations` | Alembic 迁移目录。 |
| `src/alembic.ini` | Alembic 配置。 |

## 迁移规则

表结构变化必须进入 Alembic 迁移。不要只改 `schema.py`，否则已有数据库不会自动补齐字段。

启动时后端会执行数据库初始化和迁移，使 SQLite 和 PostgreSQL 都能升级到当前结构。

迁移脚本要注意：

- SQLite 和 PostgreSQL 都要可执行。
- 不依赖某个数据库独有语法，除非有方言分支。
- 默认值和空值要考虑旧数据。
- 字段改名或删除要考虑快照恢复。

字段含义和业务关系要同步到 [数据模型参考](/reference/data-model)。恢复行为要同步到 [快照参考](/reference/snapshot)。

## 仓储规则

仓储层负责 SQL 读写和事务边界。服务层不应拼接 SQL，也不应知道具体数据库差异。

新增数据库支持时，应优先保持仓储接口不变，只扩展连接和迁移兼容。

## 快照

快照是应用级备份，不是数据库文件备份。它应包含除管理员密码外的应用业务数据，并能在 SQLite 和 PostgreSQL 之间迁移。

快照恢复后，数据库仍是唯一真相。EMQX 等外部系统应由后端根据恢复后的数据库状态重新同步。

快照涉及客户端 MQTT 凭据时，还要对照 [MQTT 协议](./mqtt-protocol) 和 [客户端接入时序](/reference/client-lifecycle)。

## 连接池

连接池由 SQLAlchemy 管理。PostgreSQL 会受益于连接池；SQLite 部署更偏轻量本地使用。

后端启动时数据库可能暂时不可用，尤其是 PostgreSQL 容器首次启动。应用会重试连接，超时后才退出。

## 相关文档

- [后端](./backend)
- [数据模型参考](/reference/data-model)
- [快照参考](/reference/snapshot)
- [环境变量参考](/reference/env)
- [Docker 部署](/deploy/)
