# Downloads

Download APIs support either an admin session or a short-lived scoped download token.

## Client artifacts

Client artifacts support two sources:

- `github_release`: uses the current server version from `src/pyproject.toml`, looks up release tag `v{version}`, and expects `wfm-client-{goos}-{goarch}-v{version}.zip`. When found, the API returns `download_url` and the browser downloads directly from GitHub.
- `local_build`: builds a zip from the local Go client source tree and serves it through the backend download endpoint.

If the GitHub release tag or target asset does not exist, the API returns a business error instead of falling back to another version.

## File token kinds

| kind | resource |
| --- | --- |
| `client_artifact` | client artifact id |
| `config_bulk_package` | bulk package id |
| `snapshot_export` | snapshot id |

MCP download tools return URLs containing 5-minute scoped tokens. MCP does not transfer file bytes.
