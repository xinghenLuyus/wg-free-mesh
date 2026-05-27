# MCP 参考

MCP 入口是 `/mcp`。认证方式是：

```http
Authorization: Bearer <mcp-token>
```

MCP 的目标是让 AI 能读懂当前系统状态，并在用户确认后执行有限写操作。

## 资源

| Resource URI | 作用 |
| --- | --- |
| `wfm://help/overview` | MCP 服务概览、认证方式、权限边界和推荐首次调用。 |
| `wfm://help/tool-index` | 工具列表和每个工具的用途。 |
| `wfm://help/workflows` | 常见工作流示例。 |
| `wfm://schema/payloads` | 写工具 payload 语义说明。 |
| `wfm://system/status` | 系统状态资源。 |
| `wfm://configs` | 配置列表资源。 |

## 只读工具

| 工具 | 作用 |
| --- | --- |
| `read_system_status` | 读取系统状态、节点统计、MQTT 状态和异常摘要。 |
| `read_configs` | 列出配置。 |
| `read_config` | 读取单个配置。 |
| `read_config_overview` | 读取配置概览投影。 |
| `read_nodes` | 列出配置下端点。 |
| `read_node_workspace` | 读取端点工作区。 |
| `read_mesh_workspace` | 读取端点视角的 Mesh 工作区。 |
| `read_mesh_validation` | 校验配置 Mesh 拓扑。 |
| `read_endpoint_status` | 读取动态端点运行状态。 |
| `read_endpoint_logs` | 读取端点控制日志。 |
| `read_sync_status` | 读取配置下同步状态。 |
| `read_node_sync_status` | 读取单端点同步状态。 |
| `read_wg_preview` | 读取生成的 WireGuard 或 AmneziaWG 配置文本。 |
| `read_client_download_options` | 读取客户端下载选项。 |
| `read_config_bulk_options` | 读取配置批量下载选项。 |
| `read_port_forward_rules` | 读取端口转发规则。 |
| `read_snapshots` | 读取快照元数据。 |

## 写工具

写工具需要 `write` token，并且每次执行都需要 MCP 客户端确认。

| 工具 | 作用 |
| --- | --- |
| `write_create_config` | 创建配置。 |
| `write_update_config` | 更新配置。 |
| `write_delete_config` | 删除配置。 |
| `write_create_node` | 创建端点。 |
| `write_update_node` | 更新端点。 |
| `write_delete_node` | 删除端点。 |
| `write_create_tag` | 创建标签。 |
| `write_apply_tag` | 应用标签到端点。 |
| `write_delete_tag` | 删除标签。 |
| `write_create_peer_link_group` | 创建双向 Mesh 对。 |
| `write_update_peer_link_group` | 更新双向 Mesh 对。 |
| `write_delete_peer_link_group` | 删除双向 Mesh 对。 |
| `write_quick_generate_mesh` | 快速组网，会删除并重建配置下 Mesh 对。 |
| `write_sync_node` | 同步单端点。 |
| `write_sync_all` | 同步所有可同步端点。 |
| `write_endpoint_control` | 发送 `start`、`stop`、`push_config`、`wg_show`。 |
| `write_probe_endpoints` | 探测动态端点。 |
| `write_create_bind_command` | 创建客户端绑定命令。 |
| `write_reset_client` | 重置客户端状态并撤销 MQTT 凭据。 |
| `write_create_port_forward_rule` | 创建端口转发规则。 |
| `write_set_port_forward_rule_enabled` | 启用或禁用端口转发规则。 |
| `write_delete_port_forward_rule` | 删除端口转发规则。 |
| `write_build_client_artifact` | 构建或获取客户端产物，返回下载 URL。 |
| `write_create_config_bulk_package` | 创建配置批量下载包，返回下载 URL。 |
| `write_export_snapshot` | 导出已有快照，返回 5 分钟下载 URL。 |

## 不通过 MCP 暴露的能力

以下能力必须在系统页面手动执行：

- 创建快照
- 导入快照
- 恢复快照
- 删除快照
- 输入或处理快照密码

## 追问与确认

部分写工具支持 MCP elicitation 追问缺失参数，例如客户端下载目标、配置批量下载节点列表、快照 ID。

追问只负责补齐参数，不代表执行。真正写入前仍会进入确认流程。

## 审计

MCP 调用写入审计日志，可在 AI 接入页面按时间、token 名称和目标接口检索，也可以按时间范围清理。
