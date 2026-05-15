# infrastructure

`infrastructure/` 保存外部资源适配的兼容入口。

## 当前内容

- `__init__.py`：包标记文件。
- `database.py`
  - re-export `app.data.database` 和 `app.data.paths` 的稳定入口。
  - 旧调用方可以继续读取 `init_database()`、`connect()`、`data_dir()`、`wireguard_dir()`。

## 约定

- 业务规则不放在这里。
- 新增数据库实现放在 `app/data/`，不要继续往这里堆实现。
