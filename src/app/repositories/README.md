# repositories

`repositories/` 保存数据访问实现。

## 当前内容

- `memory.py`：用于早期联调的内存仓储。

## 约定

- 内存仓储不是最终实现。
- 数据库模型确定后替换为 SQLAlchemy 仓储，并补充 Alembic migration。

