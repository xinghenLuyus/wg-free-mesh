# API 契约原则

## 基本原则

- API 版本从 `/api/v1` 开始。
- 所有响应使用统一 envelope。
- 所有错误使用结构化错误。
- 前端不得解析后端内部异常文本。
- 后端返回资源当前最终状态，前端以此刷新 UI。

## 响应格式建议

成功：

```json
{
  "success": true,
  "data": {},
  "meta": {}
}
```

失败：

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数不合法",
    "fields": {
      "name": "名称不能为空"
    }
  }
}
```

## 错误码分类

- `AUTH_REQUIRED`
- `PERMISSION_DENIED`
- `VALIDATION_ERROR`
- `RESOURCE_NOT_FOUND`
- `RESOURCE_CONFLICT`
- `STATE_CONFLICT`
- `OPERATION_FAILED`
- `EXTERNAL_SERVICE_ERROR`

## API 资源建议

### Auth

- `POST /api/v1/auth/setup`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### Configs

- `GET /api/v1/configs`
- `POST /api/v1/configs`
- `GET /api/v1/configs/{config_id}`
- `PATCH /api/v1/configs/{config_id}`
- `DELETE /api/v1/configs/{config_id}`

### Nodes

- `GET /api/v1/configs/{config_id}/nodes`
- `POST /api/v1/configs/{config_id}/nodes`
- `GET /api/v1/nodes/{node_id}`
- `PATCH /api/v1/nodes/{node_id}`
- `DELETE /api/v1/nodes/{node_id}`

### Mesh Links

- `GET /api/v1/configs/{config_id}/links`
- `POST /api/v1/configs/{config_id}/links`
- `PATCH /api/v1/links/{link_id}`
- `DELETE /api/v1/links/{link_id}`

### Apply

- `GET /api/v1/configs/{config_id}/apply/status`
- `POST /api/v1/configs/{config_id}/apply`
- `POST /api/v1/configs/{config_id}/apply/sync`

### Endpoints

- `GET /api/v1/configs/{config_id}/endpoints`
- `POST /api/v1/endpoints/{node_id}/control`
- `GET /api/v1/endpoints/{node_id}/logs`
- `POST /api/v1/endpoints/{node_id}/enrollment`

## 前端调用约束

- 不拼装业务路径以外的 MQTT topic。
- 不提交后端未声明字段。
- 不根据前端缓存直接判断资源可操作性。
- 写操作后必须使用后端返回值更新状态。

