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
- `PUT /api/v1/configs/{config_id}`
- `DELETE /api/v1/configs/{config_id}`
- `GET /api/v1/configs/{config_id}/overview`

### Nodes

- `GET /api/v1/configs/{config_id}/nodes`
- `POST /api/v1/configs/{config_id}/nodes`
- `GET /api/v1/nodes/{node_id}`
- `PUT /api/v1/nodes/{node_id}`
- `DELETE /api/v1/nodes/{node_id}`
- `POST /api/v1/configs/{config_id}/nodes/suggest-ip`
- `POST /api/v1/configs/{config_id}/nodes/validate-ip`
- `POST /api/v1/nodes/keys/generate`
- `POST /api/v1/nodes/keys/derive-public`

### Tags

- `GET /api/v1/configs/{config_id}/tags`
- `POST /api/v1/configs/{config_id}/tags`
- `POST /api/v1/configs/{config_id}/tags/apply`
- `DELETE /api/v1/configs/{config_id}/tags/{tag_name}`
- `PUT /api/v1/nodes/{node_id}/tags`
- `DELETE /api/v1/nodes/{node_id}/tags/{tag_name}`
- 标签创建、删除、批量应用和端点归属变更都由后端承担业务一致性，前端只提交用户选择。

### Mesh

- `GET /api/v1/configs/{config_id}/peer-links`
- `POST /api/v1/configs/{config_id}/peer-links`
- `PUT /api/v1/peer-links/{group_id}`
- `DELETE /api/v1/peer-links/{group_id}`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/mesh-workspace`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/peer-link-draft`
- `POST /api/v1/peer-links/psk/generate`
- `POST /api/v1/configs/{config_id}/mesh/validate`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/wg-preview`

### Sync

- `GET /api/v1/configs/{config_id}/sync-status`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/sync-status`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`
- `PUT /api/v1/configs/{config_id}/nodes/{node_id}/applied-conf`
- `POST /api/v1/configs/{config_id}/nodes/{node_id}/sync`
- `POST /api/v1/configs/{config_id}/sync-all`
- `POST /api/v1/configs/{config_id}/nodes/{node_id}/download-token`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/download-package`

### Endpoints

- `GET /api/v1/configs/{config_id}/endpoint/runtime-snapshot`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/status`
- `POST /api/v1/configs/{config_id}/nodes/{node_id}/bind-command`
- `POST /api/v1/configs/{config_id}/nodes/{node_id}/reset-client`
- `GET /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/logs`
- `POST /api/v1/configs/{config_id}/nodes/{node_id}/endpoint/control`
- `POST /api/v1/configs/{config_id}/endpoint/probe-batch`

### Tool Downloads

- `GET /api/v1/tools/download/client-options`
- `POST /api/v1/tools/download/client-artifacts/build`
- `GET /api/v1/tools/download/client-artifacts/{artifact_id}`
- `GET /api/v1/tools/download/config-bulk/options`
- `POST /api/v1/tools/download/config-bulk/package`
- `GET /api/v1/tools/download/config-bulk/{package_id}`

### Client And Internal

- `POST /api/client/v1/bind`
- `POST /api/internal/emqx/authz`

## 前端调用约束

- 不拼装业务路径以外的 MQTT topic。
- 不提交后端未声明字段。
- 不根据前端缓存直接判断资源可操作性。
- 写操作后必须使用后端返回值更新状态。
