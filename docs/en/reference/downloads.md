# Downloads and File Tokens

Download capabilities fall into three groups:

- Endpoint config text downloads.
- Backend-generated file downloads.
- Short-lived download URLs returned by MCP.

## Endpoint Config Text

To download an endpoint config:

1. Call `/api/v1/configs/{config_id}/nodes/{node_id}/download-token` to create a download token.
2. Download the config from the returned `download_path`.

The token is bound to that `config_id + node_id` and cannot download another endpoint config.

## Client artifacts

Client artifacts support two sources:

- `github_release`: uses the current server version from `src/pyproject.toml`, looks up release tag `v{version}`, and expects `wfm-client-{goos}-{goarch}-v{version}.zip`. When found, the API returns `download_url` and the browser downloads directly from GitHub.
- `local_build`: builds a zip from the local Go client source tree and serves it through the backend download endpoint.

If the GitHub release tag or target asset does not exist, the API returns a business error instead of falling back to another version.

The copied bash download command uses a smaller permission boundary:

- `github_release`: the frontend does not ask the backend for a grant. It builds the GitHub Release asset URL from the current version, system, and architecture. The copied command only runs `curl` and `unzip`.
- `local_build`: the frontend calls a download grant endpoint. The backend reuses the client artifact build logic, creates or locates the zip, then issues a 5-minute `client_artifact` file token. The copied command contains only the scoped file URL, not the administrator session token.

Build or fetch an artifact:

```http
POST /api/v1/tools/download/client-artifacts/build
```

Create a scoped download grant for a local build artifact:

```http
POST /api/v1/tools/download/client-artifacts/download-grant
```

Request body:

```json
{
  "source": "local_build",
  "goos": "linux",
  "goarch": "amd64"
}
```

The grant response includes `filename`, `download_path`, `download_token`, and `download_token_expires_at`. The token scope is:

```text
kind=client_artifact
resource_id={artifact_id}
```

Download the local artifact:

```http
GET /api/v1/tools/download/client-artifacts/{artifact_id}
```

The download endpoint accepts either an authenticated admin session or a file download token with `kind=client_artifact`.

GitHub Release artifacts do not use this endpoint; their `download_url` points directly to the GitHub Release asset.

Example copied command for GitHub Release:

```bash
curl -fL -o 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' 'https://github.com/xinghenLuyus/wg-free-mesh/releases/download/v1.0.0-rc.1/wfm-client-linux-amd64-v1.0.0-rc.1.zip' && unzip -oq 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' -d 'wfm-client-linux-amd64-v1.0.0-rc.1'
```

Example copied command for local build:

```bash
curl -fL -o 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' 'https://wfm.example.com/api/v1/tools/download/client-artifacts/local_build-...-linux-amd64?download_token=xxxxx' && unzip -oq 'wfm-client-linux-amd64-v1.0.0-rc.1.zip' -d 'wfm-client-linux-amd64-v1.0.0-rc.1'
```

## Bulk config packages

Create a package:

```http
POST /api/v1/tools/download/config-bulk/package
```

Download the package:

```http
GET /api/v1/tools/download/config-bulk/package/{package_id}
```

Creating a new bulk package replaces the previous temporary package.

## Snapshot Export

Export a snapshot with:

```http
GET /api/v1/backups/export/{snapshot_id}
```

MCP `write_export_snapshot` returns a five-minute `snapshot_export` download URL and does not transfer snapshot file contents.

## File Token Rules

A file token is bound to:

```text
kind + resource_id
```

Supported values are:

| kind | resource_id |
| --- | --- |
| `client_artifact` | `artifact_id` |
| `config_bulk_package` | `package_id` |
| `snapshot_export` | `snapshot_id` |

An expired token returns `INVALID_DOWNLOAD_TOKEN`; a token used for another resource returns `DOWNLOAD_TOKEN_SCOPE_MISMATCH`.
