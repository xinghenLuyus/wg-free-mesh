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

复制 bash 下载命令时使用更小的权限边界：

- `github_release`：前端不请求后端授权，直接按当前版本、系统和架构拼出 GitHub Release asset URL。复制出的命令只包含 `curl` 下载和 `unzip` 解压。
- `local_build`：前端调用下载授权接口，后端复用客户端下载构建逻辑生成或定位 zip，然后签发 5 分钟有效的 `client_artifact` 文件 token。复制出的命令只包含带 `download_token` 的文件 URL，不包含管理员会话 token。

下载授权接口：

```http
POST /api/v1/tools/download/client-artifacts/download-grant
```

请求体与构建接口一致：

```json
{
  "source": "local_build",
  "goos": "linux",
  "goarch": "amd64"
}
```

返回值包含 `filename`、`download_path`、`download_token` 和 `download_token_expires_at`。该 token 的 scope 固定为：

```text
kind=client_artifact
resource_id={artifact_id}
```

下载接口：

```http
GET /api/v1/tools/download/client-artifacts/{artifact_id}
```

下载接口支持管理员会话认证，也支持 `kind=client_artifact` 的文件下载 token。

GitHub Release 来源不使用该下载接口；接口返回的 `download_url` 是 GitHub Release asset URL。

复制出的 bash 命令示例：

```bash
curl -fL -o 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' 'https://github.com/xinghenLuyus/wg-free-mesh/releases/download/v1.0.0-rc.1/wfm-client-linux-amd64-v1.0.0-rc.1.zip' && unzip -oq 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' -d 'wfm-client-linux-amd64-v1.0.0-rc.1'
```

本地构建源示例：

```bash
curl -fL -o 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' 'https://wfm.example.com/api/v1/tools/download/client-artifacts/local_build-...-linux-amd64?download_token=xxxxx' && unzip -oq 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' -d 'wfm-client-linux-amd64-v1.0.0-rc.1'
```

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
