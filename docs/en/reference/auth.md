# Authentication and Permissions

WG Free Mesh has three token classes: administrator session tokens, download tokens, and MCP tokens. They serve different purposes and are not interchangeable.

## Administrator Session Token

Administrator login returns a Bearer token:

```http
Authorization: Bearer <access-token>
```

The session token authorizes console business APIs. Its default lifetime is controlled by `WFM_AUTH_TOKEN_EXPIRE_MINUTES`.

## Download Token

Download tokens authorize file downloads only and grant no business API permissions.

Two download-token forms are available:

| Type | Purpose | Bound scope |
| --- | --- | --- |
| Endpoint config token | Download one endpoint config text | `config_id + node_id` |
| File download token | Download one backend file | `kind + resource_id` |

Supported file-token `kind` values are:

- `client_artifact`
- `config_bulk_package`
- `snapshot_export`

The default lifetime is five minutes and is controlled by `WFM_AUTH_DOWNLOAD_TOKEN_EXPIRE_MINUTES`.

## MCP Token

MCP tokens authorize `/mcp` and are passed in a header:

```http
Authorization: Bearer <mcp-token>
```

Permissions are:

- `read`: resources and `read_*` tools only.
- `write`: both `read_*` and `write_*` tools; write operations still require confirmation.

MCP tokens are stored in plaintext in the database so the system can identify, display, revoke, and audit them.

## Source Restrictions

After `WFM_PUBLIC_ORIGIN` is configured in production, the system validates both:

- The request `Host` must equal the primary origin Host.
- A browser `Origin`, when present, must be in the allowed origin list.

`WFM_ENABLE_DEV_TEST_API=true` skips production source restrictions and registers development endpoints. It must remain disabled in production.
