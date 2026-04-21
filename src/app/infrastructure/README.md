# infrastructure

`infrastructure/` 保存数据库、MQTT、文件系统等外部资源适配。

## 当前内容

- `__init__.py`：包标记文件。
- `database.py`
  - `connect()`：创建 SQLite 连接。
  - `init_database()`：初始化数据目录与建表。
  - `data_dir()` / `backups_dir()` / `wireguard_dir()`：运行时文件目录定位。

## 约定

- 业务规则不放在这里。
- 后续 SQLAlchemy/Alembic 落地时从这里收敛数据库 Session 管理。
