# 错误码

错误响应统一包含：

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

## 通用

| 错误码 | 说明 |
| --- | --- |
| `VALIDATION_ERROR` | 请求参数校验失败。 |
| `PUBLIC_HOST_REJECTED` | 请求 Host 不在正式访问来源内。 |
| `PUBLIC_ORIGIN_REJECTED` | 浏览器 Origin 不在允许来源内。 |

## 认证

| 错误码 | 说明 |
| --- | --- |
| `AUTH_SETUP_REQUIRED` | 系统尚未初始化管理员密码。 |
| `AUTH_ALREADY_INITIALIZED` | 管理员密码已经初始化。 |
| `AUTH_REQUIRED` | 缺少管理员认证。 |
| `AUTH_FAILED` | 用户名、密码或当前密码错误。 |
| `ADMIN_PASSWORD_INVALID` | 业务操作中的管理员密码校验失败。 |
| `INVALID_TOKEN` | token 无效。 |
| `TOKEN_EXPIRED` | token 过期。 |
| `PASSWORD_UNCHANGED` | 新密码不能与当前密码相同。 |

## 下载

| 错误码 | 说明 |
| --- | --- |
| `DOWNLOAD_TOKEN_REQUIRED` | 下载接口缺少 token。 |
| `INVALID_DOWNLOAD_TOKEN` | 下载 token 无效。 |
| `INVALID_DOWNLOAD_RESOURCE` | 下载资源类型无效。 |
| `DOWNLOAD_TOKEN_SCOPE_MISMATCH` | token 与目标文件不匹配。 |
| `CLIENT_ARTIFACT_NOT_FOUND` | 客户端产物不存在。 |
| `GITHUB_RELEASE_ASSET_NOT_FOUND` | 当前版本没有匹配的 GitHub Release 客户端包。 |
| `GITHUB_RELEASE_DOWNLOAD_FAILED` | GitHub Release 客户端包检查失败。 |
| `CONFIG_BULK_PACKAGE_NOT_FOUND` | 配置批量包不存在。 |
| `CONFIG_BULK_EMPTY_SELECTION` | 未选择可下载端点。 |
| `CONFIG_BULK_NODE_NOT_READY` | 端点没有可下载的 staged 配置。 |

## 配置与端点

| 错误码 | 说明 |
| --- | --- |
| `CONFIG_NOT_FOUND` | 配置不存在。 |
| `CONFIG_NAME_EXISTS` | 配置名称重复。 |
| `INVALID_CONFIG_NAME` | 配置名称不合法。 |
| `INVALID_SUBNET` | 配置虚拟网段不合法。 |
| `NODE_NOT_FOUND` | 端点不存在。 |
| `NODE_CONFIG_MISMATCH` | 端点不属于指定配置。 |
| `NODE_DISABLED` | 禁用端点不支持当前操作。 |
| `INVALID_NODE_NAME` | 端点名称不合法。 |
| `INVALID_VIRTUAL_IP` | 虚拟 IP 不合法。 |
| `IP_POOL_EXHAUSTED` | 虚拟网段没有可用地址。 |
| `INVALID_TAG` | 标签不合法。 |

## Mesh 与同步

| 错误码 | 说明 |
| --- | --- |
| `INVALID_PEER_LINK` | Mesh 对不合法。 |
| `PEER_LINK_NOT_FOUND` | Mesh 对不存在。 |
| `INVALID_ALLOWED_IPS` | AllowedIPs 不合法。 |
| `INVALID_ENDPOINT` | 手动 Endpoint 缺少 Host 或 Port。 |
| `TOPOLOGY_INVALID` | 拓扑校验未通过，不能同步。 |
| `NO_STAGED_CONFIG` | 没有待推送配置。 |
| `CONTROL_LOG_NOT_FOUND` | 控制日志不存在。 |

## 快速组网

| 错误码 | 说明 |
| --- | --- |
| `INVALID_QUICK_MESH_MODE` | 快速组网模式无效。 |
| `INVALID_ENDPOINT_FAMILY` | Endpoint 地址族无效。 |
| `QUICK_MESH_NOT_ENOUGH_NODES` | 启用端点少于两个。 |
| `QUICK_MESH_HUB_REQUIRED` | 网关节点缺失或不可用。 |
| `QUICK_MESH_GATEWAY_REQUIRED` | Free Mesh 至少需要一个可用 gateway。 |
| `QUICK_MESH_LEAF_INVALID` | Leaf 端点无效。 |
| `QUICK_MESH_NODE_ROLE_CONFLICT` | 端点不能同时是 gateway 和 leaf。 |
| `QUICK_MESH_LEAF_GATEWAY_INVALID` | Leaf 指向了未选择的 gateway。 |
| `QUICK_MESH_NODE_UNASSIGNED` | 启用端点未分配角色。 |

## AmneziaWG

| 错误码 | 说明 |
| --- | --- |
| `INVALID_TUNNEL_PROTOCOL` | 隧道协议无效。 |
| `INVALID_AWG_PARAMETER` | AWG 参数超出范围。 |
| `INVALID_AWG_H_RANGE` | H 参数格式、范围或重叠关系无效。 |
| `INVALID_AWG_J_RANGE` | Jmax 必须大于 Jmin。 |

## MQTT 与客户端

| 错误码 | 说明 |
| --- | --- |
| `MQTT_DISABLED` | MQTT 服务被部署配置关闭。 |
| `MQTT_TLS_CA_NOT_READY` | 客户端 TLS CA 证书尚未准备好。 |
| `MQTT_CONTROL_UNAVAILABLE` | MQTT 控制通道不可用。 |
| `INVALID_ACTION` | 控制动作无效。 |
| `CLIENT_BIND_STATIC_NODE` | 静态端点不能绑定客户端。 |
| `CLIENT_BIND_TOKEN_INVALID` | 绑定 token 无效。 |
| `CLIENT_BIND_TOKEN_USED` | 绑定 token 已使用。 |
| `CLIENT_BIND_TOKEN_EXPIRED` | 绑定 token 过期。 |
| `CLIENT_BIND_NOT_ALLOWED` | 当前端点不允许绑定。 |

## 端口转发

| 错误码 | 说明 |
| --- | --- |
| `PORT_FORWARD_SAME_NODE` | From 和 To 端点不能相同。 |
| `PORT_FORWARD_TO_PLATFORM_INVALID` | 目的系统必须是 Linux 或 macOS。 |
| `PORT_FORWARD_PROTOCOL_INVALID` | 协议必须是 TCP、UDP 或 all。 |
| `PORT_FORWARD_TO_PORT_IN_USE` | To 端口已被其他规则管理。 |
| `PORT_FORWARD_NOT_FOUND` | 端口转发规则不存在。 |
| `PORT_FORWARD_NODE_INVALID` | 端点不在配置中或未启用。 |
| `PORT_FORWARD_VIRTUAL_IP_REQUIRED` | 端点缺少虚拟 IP。 |
| `PORT_FORWARD_PORT_INVALID` | 端口不合法。 |
| `PORT_FORWARD_IPV4_REQUIRED` | 端口转发当前需要 IPv4 虚拟 IP。 |

## 快照

| 错误码 | 说明 |
| --- | --- |
| `SNAPSHOT_NOT_FOUND` | 快照不存在。 |
| `SNAPSHOT_INVALID_ARCHIVE` | 快照压缩包无效。 |
| `SNAPSHOT_IMPORT_FAILED` | 快照导入后未被索引。 |
| `SNAPSHOT_RESTORE_UNSAFE_PATH` | 恢复目标路径不安全。 |
| `SNAPSHOT_PASSWORD_INVALID` | 快照解密密码错误。 |

## MCP

| 错误码 | 说明 |
| --- | --- |
| `MCP_TOKEN_NAME_REQUIRED` | MCP token 名称必填。 |
| `MCP_TOKEN_PERMISSION_INVALID` | MCP token 权限必须是 read 或 write。 |
| `MCP_TOKEN_EXPIRY_INVALID` | MCP token 过期时间无效。 |
| `MCP_TOKEN_NOT_FOUND` | MCP token 不存在。 |
| `MCP_AUDIT_RANGE_INVALID` | 审计清理时间范围无效。 |
