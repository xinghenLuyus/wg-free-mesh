# repositories

`repositories/` 保存数据访问实现。

## 当前内容

- `sqlite.py`
  - `SQLiteStore`：当前 SQLite 主仓储，承载配置、节点、Mesh、同步态、运行态、快照和系统设置读写。
  - `normalize_allowed_ips(...)`：标准化并校验 AllowedIPs。
  - `delete_setting(...)` / `read_setting(...)` / `write_setting(...)`：系统设置存取。
- `naming.py`
  - `validate_config_name(...)`：校验配置名。
  - `config_artifact_name_segment(...)`：把文件名片段收敛成安全字符。
  - `node_config_artifact_stem(...)`：按 `配置名-节点名` 生成 `.conf` 文件 stem，并对非 ASCII 做百分号编码。
- `row_mappers.py`
  - `config_from_row(...)` / `node_from_row(...)` / `peer_link_from_row(...)`：数据库行映射。
  - `state_from_row(...)` / `runtime_from_row(...)` / `log_from_row(...)` / `snapshot_from_row(...)`：同步态、运行态、日志与快照映射。

## 约定

- 数据库模型确定后替换为 SQLAlchemy 仓储，并补充 Alembic migration。
- 优先按仓储职责拆模块，不把业务命名、Mesh 规则、WireGuard 配置生成等逻辑塞进通用 `util`。
