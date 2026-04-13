# infrastructure

`infrastructure/` 保存数据库、MQTT、文件系统等外部资源适配。

## 当前内容

- `database.py`：SQLite 连接、建表和种子数据。

## 约定

- 业务规则不放在这里。
- 后续 SQLAlchemy/Alembic 落地时从这里收敛数据库 Session 管理。

