# AI 接入

AI 接入用于把 WG Free Mesh 暴露给支持 MCP 的 AI 工具。接好以后，可以让 AI 查询系统状态、检查端点、生成下载链接，或者在你确认后执行有限写操作。

## 准备 Token

在控制台进入：

```text
工具列表 -> 其它 -> AI 接入
```

创建一个 MCP Token：

- 只想查询系统状态，选择 `read`。
- 需要让 AI 创建配置、快速组网、生成下载链接，选择 `write`。
- 设置有效期。
- 复制生成的 token。

`write` token 不代表 AI 可以直接改系统。真正影响业务的操作仍然需要你在 MCP 客户端里确认。

## MCP 端点

MCP 地址就是系统访问地址后面加 `/mcp`。

本机 Docker 默认：

```text
http://localhost:8000/mcp
```

生产环境示例：

```text
https://wfm.example.com/mcp
```

认证方式使用 HTTP Header：

```http
Authorization: Bearer <mcp-token>
```

如果你的 AI 工具有 MCP 配置界面，通常填写：

| 配置项 | 填写内容 |
| --- | --- |
| Name | `wfm` |
| Type / Transport | HTTP / Streamable HTTP |
| URL | `http://localhost:8000/mcp` 或 `https://wfm.example.com/mcp` |
| Header | `Authorization: Bearer <mcp-token>` |

如果工具使用 JSON 配置，常见写法类似：

```json
{
  "mcpServers": {
    "wfm": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer wfm_mcp_xxx"
      }
    }
  }
}
```

不同 AI 客户端的字段名可能略有差异，但核心就是 URL 加 Bearer Token。

## 第一次怎么验证

接入后，先让 AI 做只读检查：

```text
你已经接入 WG Free Mesh 的 MCP。先读取 wfm://help/overview 和 wfm://help/tool-index，然后告诉我当前系统有哪些可用能力，不要执行任何写操作。
```

再让它读取系统状态：

```text
请通过 WFM MCP 查看当前系统状态，列出配置数量、端点数量、在线端点数量和 MQTT 状态。
```

如果这两步能返回内容，说明 MCP 接入基本正常。

## 可以直接这样问

查询状态：

```text
帮我检查 WG Free Mesh 当前有哪些端点离线，按配置分组列出来，并说明你依据了哪些状态字段。
```

查看配置：

```text
列出当前所有配置，告诉我每个配置的协议、虚拟网段、节点数量和 Mesh 对数量。
```

生成客户端下载链接：

```text
帮我生成 Windows amd64 客户端下载链接。如果需要选择构建目标，直接追问我。
```

导出已有快照：

```text
帮我导出最近一个快照，返回下载链接。不要创建新快照，也不要恢复快照。
```

快速组网前评估：

```text
检查配置 mesh-main 是否适合生成 Free Mesh。先列出会被删除和重新生成的 Mesh 对，不要直接执行。
```

执行写操作：

```text
为配置 mesh-main 执行 Free Mesh 快速组网，开启 PSK。执行前给我确认摘要，等我确认后再继续。
```

创建配置：

```text
帮我创建一个名为 office-mesh 的 WireGuard 配置，虚拟网段使用 10.77.0.0/24，默认监听端口 51820。
```

这些提示词可以直接给 Claude Code、OpenClaw 或其他支持 MCP 的客户端使用。写操作是否能弹出确认窗口，取决于客户端是否支持 MCP 的确认交互。

## 下载链接怎么工作

客户端下载、配置批量下载、快照导出不会把文件内容塞进 AI 对话。

MCP 会返回一个 5 分钟有效的下载 URL。点击 URL 会打开空白页并触发下载。这个 URL 只能下载对应的那一个文件，不能拿去访问其他文件。

## 审计记录

AI 接入页面可以查看 MCP 调用审计。你可以按：

- 时间。
- Token 名称。
- 接口或工具名称。

来检索调用记录，也可以按时间范围清理审计。

排查 AI 做过什么时，先看审计记录。写操作会记录影响摘要。

## 不要让 AI 做这些事

这些操作必须回到控制台手动完成：

- 创建快照。
- 导入快照。
- 恢复快照。
- 删除快照。
- 输入管理员密码。
- 输入快照密码。

AI 可以帮你导出已有快照的下载链接，但不能处理快照密码，也不能执行恢复。

## 常见问题

### 连接不上 MCP

先检查三件事：

1. URL 是否是 `/mcp`，不是 `/api/v1/...`。
2. Header 是否是 `Authorization: Bearer <mcp-token>`。
3. 当前访问地址是否被系统允许。生产环境要使用 `WFM_PUBLIC_ORIGIN` 对应的地址。

### AI 说没有写权限

你使用的是 `read` token。需要执行写操作时，重新创建 `write` token。

### 写操作没有真正执行

写操作需要 MCP 客户端支持确认流程。AI 补齐参数不等于确认执行，必须完成确认后才会真正写入系统。

更多工具和资源清单见 [MCP 参考](/reference/mcp)。
