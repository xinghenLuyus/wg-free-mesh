# internal routers

`src/app/api/internal/routers/` 保存后端内部基础设施接口。

## 当前模块

- `emqx.py`
  - `authorize(...)`：供 EMQX 在 publish / subscribe 时回查节点级 topic 授权结果。
