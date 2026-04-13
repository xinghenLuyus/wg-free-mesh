# schemas

`schemas/` 保存 API 请求和响应模型。

## 约定

- 使用 Pydantic v2。
- 请求模型和响应模型分离。
- 不向前端暴露敏感字段。
- 修改 schema 时同步更新 `docs/API契约原则.md`。

