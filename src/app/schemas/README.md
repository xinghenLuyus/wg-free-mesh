# schemas

`schemas/` 保存 API 请求和响应模型。

## 当前内容

- `nodes.py`：当前端点模型的请求与响应 schema，使用 `NodeType`。
- `mesh.py`：当前 PeerLink 和 Mesh 校验响应 schema。

## 约定

- 使用 Pydantic v2。
- 请求模型和响应模型分离。
- 不向前端暴露未确认需要的敏感字段。
- Schema 必须跟 `app.domain.models` 当前模型保持一致，不保留旧重构残留类型。
- 修改 schema 时同步更新 `docs/API接口设计.md`，并通过 `mypy app`。
