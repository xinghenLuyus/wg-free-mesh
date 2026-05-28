# 下载与文件 token

下载能力分为三类：

- 节点配置文本下载
- 后端生成文件下载
- MCP 返回短期下载 URL

## 节点配置文本

端点配置下载流程：

1. 调用 `/api/v1/configs/{config_id}/nodes/{node_id}/download-token` 创建下载 token。
2. 使用返回的 `download_path` 下载配置。

下载 token 只绑定该 `config_id + node_id`，不能下载其他端点配置。

## 客户端产物

客户端产物支持两个来源：

- `github_release`：按 `src/pyproject.toml` 中的当前系统版本拼出 `v{version}` Release，并查找 `wfm-client-{goos}-{goarch}-v{version}.zip`。命中后接口返回 `download_url`，前端直接跳转 GitHub 下载，不经过后端缓存。
- `local_build`：服务端调用本地 Go 工具链构建 zip，并通过后端下载接口返回。

构建接口：

```http
POST /api/v1/tools/download/client-artifacts/build
```

下载接口：

```http
GET /api/v1/tools/download/client-artifacts/{artifact_id}
```

下载接口支持管理员会话认证，也支持 `kind=client_artifact` 的文件下载 token。

GitHub Release 来源不使用该下载接口；接口返回的 `download_url` 是 GitHub Release asset URL。

## 配置批量下载包

生成接口：

```http
POST /api/v1/tools/download/config-bulk/package
```

下载接口：

```http
GET /api/v1/tools/download/config-bulk/{package_id}
```

配置批量下载不复用旧包。生成新包时会替换临时产物。

## 快照导出

快照导出接口：

```http
GET /api/v1/backups/export/{snapshot_id}
```

MCP 的 `write_export_snapshot` 只返回一个 5 分钟有效的 `snapshot_export` 下载 URL，不传输文件内容。

## 文件 token 规则

文件 token 绑定：

```text
kind + resource_id
```

当前支持：

| kind | resource_id |
| --- | --- |
| `client_artifact` | `artifact_id` |
| `config_bulk_package` | `package_id` |
| `snapshot_export` | `snapshot_id` |

token 过期或 scope 不匹配时，返回 `INVALID_DOWNLOAD_TOKEN` 或 `DOWNLOAD_TOKEN_SCOPE_MISMATCH`。
