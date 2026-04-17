# repositories

`repositories/` 保存数据访问实现。

## 当前内容

- `memory.py`：用于早期联调的内存仓储。
- `sqlite.py`：SQLite 仓储主入口，负责主要读写流程协调。
- `naming.py`：配置导出命名规则，例如 `配置名-节点名` 与百分号编码。
- `row_mappers.py`：数据库 `Row` 到领域模型的转换。

## 约定

- 内存仓储不是最终实现。
- 数据库模型确定后替换为 SQLAlchemy 仓储，并补充 Alembic migration。
- 优先按仓储职责拆模块，不把业务命名、Mesh 规则、WireGuard 配置生成等逻辑塞进通用 `util`。
