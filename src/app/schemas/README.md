# schemas

`schemas/` 保存 API 请求和响应模型。

## 当前内容

- `auth.py`
  - 登录、初始化、密码修改请求。
  - 后台 token、下载 token、认证状态响应。
- `common.py`
  - 健康检查和通用操作结果模型。
- `configs.py`
  - 配置创建与读取模型。
- `mesh.py`
  - Mesh 链路、草稿、校验和预览模型。
- `nodes.py`
  - 节点创建、读取和标签相关模型。
- `settings.py`
  - 系统设置兼容模型，保留给后续更完整设置聚合使用。

## 约定

- 使用 Pydantic v2。
- 请求模型和响应模型分离。
- 不向前端暴露未确认需要的敏感字段。
- Schema 必须跟 `app.domain.models` 当前模型保持一致，不保留旧重构残留类型。
- 修改 schema 时同步更新 `docs/API接口设计.md`，并通过 `mypy app`。
