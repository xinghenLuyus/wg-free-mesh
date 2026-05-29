# API 参考

REST API 以 `/api/v1` 为主入口，统一返回：

```json
{
  "success": true,
  "data": {}
}
```

错误响应统一返回：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Readable message",
    "detail": {}
  }
}
```

## 接口分层

WFM 不是单一浏览器 API，实际有四类 HTTP 接口：

| 层级 | 前缀 | 调用方 | 说明 |
| --- | --- | --- | --- |
| 控制台 API | `/api/v1` | 浏览器控制台、受信外部调用方 | 主要业务接口，默认需要管理员 Bearer token。 |
| 客户端 API | `/api/client` | `wfmctl bind` | 只用于客户端一次性绑定，不使用管理员会话 token。 |
| 内部 API | `/api/internal` | EMQX 等内部组件 | 只允许容器内或可信网络调用，必须带内部共享密钥。 |
| 开发 API | `/api/v0` | 本地开发和自动化测试 | 仅在 `WFM_ENABLE_DEV_TEST_API=true` 时注册。 |

MCP 的 HTTP 入口是 `/mcp`，但 MCP 工具不应绕过业务服务层。MCP 的读写能力应复用控制台 API 背后的同一套服务逻辑。

## 调用约定

### 管理员会话

控制台业务 API 默认使用：

```http
Authorization: Bearer <admin-session-token>
```

登录、初始化、健康检查等少量接口可以匿名访问。下载接口还允许使用下载专用 token。

### 来源限制

正式部署下，后端会按公开访问来源和反向代理后的 Host 做访问限制。浏览器请求需要满足允许来源；无 Origin 的 CLI/curl 请求只允许主来源 Host。开发模式下限制可以放宽。

### 下载 token

客户端下载产物、配置批量包和快照导出可以使用 5 分钟有效的单文件下载 token。下载 token 只能访问绑定的资源，不能访问其它 API，也不能横向下载其它文件。

### 业务写入

写接口应遵守同一顺序：

1. 校验输入和权限。
2. 在数据库事务内修改业务数据。
3. 必要时同步 EMQX 或下发 MQTT。
4. 发布 SSE 刷新事件。
5. 返回前端可以直接展示或据此刷新页面的结果。

如果某个外部系统暂时不可用，应尽量保持数据库写入语义清晰：能落库的先落库，不能保证一致性的操作必须返回明确错误码。

## 认证 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/auth/state` | 查询初始化状态和当前会话状态。 |
| `POST` | `/api/v1/auth/setup` | 首次初始化管理员密码。 |
| `POST` | `/api/v1/auth/login` | 管理员登录，返回 Bearer token。 |
| `GET` | `/api/v1/auth/session` | 校验当前 Bearer token。 |
| `POST` | `/api/v1/auth/logout` | 前端退出登录接口。 |
| `POST` | `/api/v1/auth/password` | 修改管理员密码。 |

## 配置 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/configs` | 列出配置。 |
| `POST` | `/api/v1/configs` | 创建配置。 |
| `GET` | `/api/v1/configs/{config_id}` | 读取配置。 |
| `PUT` | `/api/v1/configs/{config_id}` | 更新配置。 |
| `DELETE` | `/api/v1/configs/{config_id}` | 删除配置。 |
| `GET` | `/api/v1/configs/{config_id}/overview` | 读取配置概览投影。 |
| `POST` | `/api/v1/configs/awg/random` | 生成配置级 AmneziaWG 参数。 |

## 端点 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/nodes` | 列出配置下端点。 |
| `POST` | `/api/v1/configs/{config_id}/nodes` | 创建端点。 |
| `GET` | `/api/v1/nodes/{node_id}` | 读取端点。 |
| `PUT` | `/api/v1/nodes/{node_id}` | 更新端点。 |
| `DELETE` | `/api/v1/nodes/{node_id}` | 删除端点。 |
| `POST` | `/api/v1/configs/{config_id}/nodes/suggest-ip` | 推荐虚拟 IP。 |
| `POST` | `/api/v1/configs/{config_id}/nodes/validate-ip` | 校验虚拟 IP。 |
| `POST` | `/api/v1/nodes/keys/generate` | 生成 WireGuard 密钥对。 |
| `POST` | `/api/v1/nodes/keys/derive-public` | 从私钥派生公钥。 |
| `POST` | `/api/v1/nodes/awg/random` | 生成端点级 AmneziaWG 参数。 |

## 标签 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/tags` | 列出标签和计数。 |
| `POST` | `/api/v1/configs/{config_id}/tags` | 创建标签。 |
| `POST` | `/api/v1/configs/{config_id}/tags/apply` | 批量给端点应用标签。 |
| `DELETE` | `/api/v1/configs/{config_id}/tags/{tag_name}` | 删除配置级标签。 |
| `PUT` | `/api/v1/nodes/{node_id}/tags` | 替换端点标签。 |
| `DELETE` | `/api/v1/nodes/{node_id}/tags/{tag_name}` | 从端点移除标签。 |

## Mesh API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/peer-links` | 列出 Mesh 对。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/mesh-workspace` | 读取端点 Mesh 工作区。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/peer-link-draft` | 生成 Mesh 对草稿。 |
| `POST` | `/api/v1/configs/{config_id}/peer-links` | 创建双向 Mesh 对。 |
| `PUT` | `/api/v1/peer-links/{group_id}` | 更新双向 Mesh 对。 |
| `DELETE` | `/api/v1/peer-links/{group_id}` | 删除双向 Mesh 对。 |
| `POST` | `/api/v1/peer-links/psk/generate` | 生成 PSK。 |
| `POST` | `/api/v1/configs/{config_id}/mesh/validate` | 校验 Mesh。 |
| `POST` | `/api/v1/configs/{config_id}/mesh/quick-generate` | 快速组网，删除并重建 Mesh 对。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/wg-preview` | 预览生成的 WG/AWG 配置。 |

## 配置应用与端点控制 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/sync-status` | 读取配置下所有端点同步态。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/sync-status` | 读取单端点同步态。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/applied-conf` | 读取已应用配置文本。 |
| `PUT` | `/api/v1/configs/{config_id}/nodes/{node_id}/applied-conf` | 保存应用配置文本。 |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/sync` | 同步单端点。 |
| `POST` | `/api/v1/configs/{config_id}/sync-all` | 同步配置下所有可同步端点。 |
| `GET` | `/api/v1/configs/{config_id}/endpoint/runtime-snapshot` | 读取运行态快照。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint/status` | 读取端点运行状态。 |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/bind-command` | 创建客户端绑定命令。 |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/reset-client` | 重置客户端绑定和 MQTT 凭据。 |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint/logs` | 读取端点控制日志。 |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint/control` | 发送 `start`、`stop`、`push_config`、`wg_show`。 |
| `POST` | `/api/v1/configs/{config_id}/endpoint/probe-batch` | 批量探测端点。 |

## 工具 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/tools/download/client-options` | 读取客户端构建选项。 |
| `POST` | `/api/v1/tools/download/client-artifacts/build` | 构建或获取客户端产物。 |
| `POST` | `/api/v1/tools/download/client-artifacts/download-grant` | 为本地构建客户端产物生成 5 分钟单文件下载 token；Release 来源不需要该接口。 |
| `GET` | `/api/v1/tools/download/client-artifacts/{artifact_id}` | 下载客户端产物。 |
| `GET` | `/api/v1/tools/download/config-bulk/options` | 读取配置批量下载选项。 |
| `POST` | `/api/v1/tools/download/config-bulk/package` | 生成配置批量下载包。 |
| `GET` | `/api/v1/tools/download/config-bulk/{package_id}` | 下载配置批量包。 |
| `GET` | `/api/v1/tools/port-forwards/configs/{config_id}` | 列出端口转发规则。 |
| `POST` | `/api/v1/tools/port-forwards/configs/{config_id}` | 创建端口转发规则。 |
| `PUT` | `/api/v1/tools/port-forwards/{rule_id}/enabled` | 启用或禁用端口转发规则。 |
| `DELETE` | `/api/v1/tools/port-forwards/{rule_id}` | 删除端口转发规则。 |

## 备份 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/backups/snapshot` | 创建快照。 |
| `GET` | `/api/v1/backups/list` | 列出快照。 |
| `GET` | `/api/v1/backups/download/{snapshot_id}` | 下载快照。 |
| `GET` | `/api/v1/backups/export/{snapshot_id}` | 导出快照。 |
| `POST` | `/api/v1/backups/restore/{snapshot_id}` | 恢复快照。 |
| `POST` | `/api/v1/backups/upload` | 上传导入快照。 |
| `POST` | `/api/v1/backups/import` | 上传导入快照。 |
| `DELETE` | `/api/v1/backups/{snapshot_id}` | 删除快照。 |
| `PUT` | `/api/v1/backups/{snapshot_id}/note` | 更新快照备注。 |

## 设置与系统 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/settings/ui` | 读取界面设置。 |
| `PUT` | `/api/v1/settings/ui` | 更新界面设置。 |
| `GET` | `/api/v1/settings/mqtt` | 读取客户端 MQTT 接入地址。 |
| `PUT` | `/api/v1/settings/mqtt` | 更新客户端 MQTT 接入地址。 |
| `POST` | `/api/v1/settings/mqtt/reset` | 重置为环境变量默认值。 |
| `POST` | `/api/v1/settings/mqtt/test` | 测试 MQTT 接入配置。 |
| `POST` | `/api/v1/settings/password` | 修改管理员密码。 |
| `GET` | `/api/v1/system/health` | 健康检查。 |
| `GET` | `/api/v1/system/timezone` | 读取时区。 |
| `GET` | `/api/v1/system/status` | 读取系统状态。 |
| `GET` | `/api/v1/events/stream` | SSE 实时事件流。 |

## 客户端和内部 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/client/bind` | 客户端使用绑定 token 换取 profile、MQTT 凭据和配置。 |
| `POST` | `/api/internal/emqx/authz` | EMQX HTTP AuthZ 回调，仅内部使用。 |
| `POST` | `/api/v0/dev/reset-bootstrap` | 开发测试接口，仅 `WFM_ENABLE_DEV_TEST_API=true` 时注册。 |
