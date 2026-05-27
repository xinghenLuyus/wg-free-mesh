# API Contract

APIs should stay stable, debuggable, and reusable by both the frontend and MCP. Before adding an endpoint, check existing resource boundaries first.

The full endpoint list is in [API Reference](/en/reference/api). If the endpoint can be called by AI, also update [MCP Reference](/en/reference/mcp) and [Security](/en/reference/security).

## Response Shape

Success:

```json
{
  "success": true,
  "data": {}
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "detail": {}
  }
}
```

The frontend should use `code` for localization. `message` is mainly for debugging.

## Auth Boundaries

Token types:

- Admin session token: console business APIs.
- Download token: one scoped file download.
- MCP token: only for `/mcp`.

They are not interchangeable.

## Resource Groups

| Group | Responsibility |
| --- | --- |
| Auth | Setup, login, session, password. |
| Configs | Config CRUD and overview. |
| Nodes | Nodes, tags, addresses, advanced parameters. |
| Mesh | Mesh pairs, topology validation, quick mesh. |
| Endpoints | Dynamic endpoint status, control, bind command. |
| Tools | Client downloads, bulk config packages, port forwarding. |
| Settings | UI, MQTT, password. |
| Backups | Snapshot create, export, import, restore, delete. |
| MCP Access | MCP tokens and audit logs. |
| System | Health, system status, SSE. |

See [API Reference](/en/reference/api) for the full list.

## Downloads

Download APIs support admin session auth and scoped file download tokens.

MCP download tools return 5-minute URLs instead of file bytes. The download token must be scoped to file type and resource ID.

## Writes

After a write changes UI state:

1. Update the database.
2. Publish SSE events.
3. Synchronize EMQX if needed.
4. Return a frontend-friendly result.

Endpoint control, sync, quick mesh, and port forwarding writes should make affected nodes explicit.

## MCP and API

MCP tools must reuse the same service-layer logic as Web APIs. They add write confirmation and audit, but they do not bypass business rules.

## Related Docs

- [API Reference](/en/reference/api)
- [Auth](/en/reference/auth)
- [Errors](/en/reference/errors)
- [MCP Reference](/en/reference/mcp)
- [Backend](./backend)
