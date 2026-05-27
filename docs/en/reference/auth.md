# Auth

WG Free Mesh uses three token types.

## Admin session token

Admin APIs use:

```http
Authorization: Bearer <access-token>
```

The default lifetime is controlled by `WFM_AUTH_TOKEN_EXPIRE_MINUTES`.

## Download token

Download tokens do not grant business API access. They are scoped to one node config or one generated file.

File download token kinds:

- `client_artifact`
- `config_bulk_package`
- `snapshot_export`

The default lifetime is 5 minutes.

## MCP token

MCP uses:

```http
Authorization: Bearer <mcp-token>
```

Permissions are `read` and `write`. Write tools still require confirmation.
