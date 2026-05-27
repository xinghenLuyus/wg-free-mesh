# API 契约

API 契约要稳定、可调试、可被前端和 MCP 复用。新增接口前先确认已有资源边界，避免把业务逻辑分散到多个近似接口里。

完整接口清单见 [API 参考](/reference/api)。如果接口会被 AI 调用，还要同步 [MCP 参考](/reference/mcp) 和 [安全边界](/reference/security)。

## 响应结构

业务 API 使用统一响应结构：

```json
{
  "success": true,
  "data": {}
}
```

错误响应：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "detail": {}
  }
}
```

前端应优先使用 `code` 做本地化展示，`message` 主要用于调试。

## 认证边界

当前有三类 token：

- 管理员会话 token：控制台业务 API。
- 下载 token：只允许下载一个绑定文件或一个生成文件。
- MCP token：只用于 `/mcp`。

三类 token 不能混用。

## 资源边界

主要 API 分组：

| 分组 | 职责 |
| --- | --- |
| Auth | 初始化、登录、会话、密码。 |
| Configs | 配置增删改查和配置概览。 |
| Nodes | 端点、标签、地址和高级参数。 |
| Mesh | Mesh 对、拓扑校验和快速组网。 |
| Endpoints | 动态端点状态、控制命令、绑定命令。 |
| Tools | 客户端下载、配置批量下载、端口转发。 |
| Settings | UI、MQTT、密码等设置。 |
| Backups | 快照创建、导出、导入、恢复、删除。 |
| MCP Access | MCP token 和调用审计。 |
| System | 健康检查、系统状态和 SSE。 |

完整接口清单见 [API 参考](/reference/api)。

## 下载接口

下载接口支持管理员会话认证，也支持单文件下载 token。

MCP 下载类工具不传输文件内容，只返回 5 分钟有效的下载 URL。下载 token 必须绑定文件类型和资源 ID，不能横向下载其他文件。

## 写操作

写操作完成后，如果影响页面状态，应：

1. 更新数据库。
2. 发布对应 SSE 事件。
3. 必要时同步 EMQX。
4. 返回可被前端直接展示或刷新页面的结果。

涉及端点控制、同步、快速组网和端口转发的写操作，应明确哪些节点会受影响。

## MCP 与 API

MCP 工具应复用同一套服务层逻辑，不应绕过 API 背后的业务规则。MCP 的写操作还需要额外确认和审计。

## 相关文档

- [API 参考](/reference/api)
- [认证与权限](/reference/auth)
- [错误码](/reference/errors)
- [MCP 参考](/reference/mcp)
- [后端](./backend)
