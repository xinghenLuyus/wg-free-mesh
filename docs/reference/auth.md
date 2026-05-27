# 认证与权限

WG Free Mesh 有三类 token：管理员会话 token、下载 token、MCP token。它们用途不同，不能混用。

## 管理员会话 token

管理员登录后得到 Bearer token：

```http
Authorization: Bearer <access-token>
```

会话 token 用于控制台业务 API。默认有效期由 `WFM_AUTH_TOKEN_EXPIRE_MINUTES` 控制。

## 下载 token

下载 token 只用于文件下载，不拥有业务 API 权限。

当前有两类下载 token：

| 类型 | 用途 | 绑定范围 |
| --- | --- | --- |
| 节点配置下载 token | 下载单个端点配置文本 | `config_id + node_id` |
| 文件下载 token | 下载单个后端文件 | `kind + resource_id` |

文件下载 token 的 `kind` 当前支持：

- `client_artifact`
- `config_bulk_package`
- `snapshot_export`

默认有效期是 5 分钟，由 `WFM_AUTH_DOWNLOAD_TOKEN_EXPIRE_MINUTES` 控制。

## MCP token

MCP token 用于 `/mcp`，通过 Header 传递：

```http
Authorization: Bearer <mcp-token>
```

权限分为：

- `read`：只能调用资源和 `read_*` 工具。
- `write`：可以调用 `read_*` 和 `write_*` 工具，但写操作仍必须确认。

MCP token 在数据库中明文保存，便于系统识别、展示、撤销和审计。

## 来源限制

生产环境设置 `WFM_PUBLIC_ORIGIN` 后，系统会同时校验：

- 请求 `Host` 必须等于主来源 Host。
- 浏览器 `Origin` 如存在，必须在允许来源内。

`WFM_ENABLE_DEV_TEST_API=true` 时跳过正式来源限制，并注册开发接口。生产部署必须保持关闭。
