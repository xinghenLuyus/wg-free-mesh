# API

The REST API uses `/api/v1` as the main prefix.

Successful responses use:

```json
{ "success": true, "data": {} }
```

Error responses use:

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

## Main groups

| Group | Prefix | Purpose |
| --- | --- | --- |
| Auth | `/api/v1/auth` | Setup, login, session, password. |
| Configs | `/api/v1/configs` | Mesh config CRUD and overview. |
| Nodes | `/api/v1/configs/{config_id}/nodes`, `/api/v1/nodes` | Node CRUD, tags, keys, AWG random params. |
| Mesh | `/api/v1/peer-links`, `/api/v1/configs/{config_id}/mesh` | Peer links, validation, quick mesh. |
| Endpoint control | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint` | Runtime status, logs, MQTT control. |
| Tools | `/api/v1/tools` | Client downloads, bulk config packages, port forwarding. |
| Backups | `/api/v1/backups` | Snapshot create, list, export, restore, import, delete. |
| Settings | `/api/v1/settings` | UI, MQTT access settings, password. |
| System | `/api/v1/system`, `/api/v1/events` | Health, status, timezone, SSE. |
| MCP access | `/api/v1/mcp-access` | MCP tokens and audit logs. |

Client binding uses `/api/client/bind`. EMQX internal authorization uses `/api/internal/emqx/authz`.

## API Layers

WFM exposes multiple HTTP layers:

| Layer | Prefix | Caller | Notes |
| --- | --- | --- | --- |
| Console API | `/api/v1` | Browser console and trusted external callers | Main business API. Usually requires administrator Bearer token. |
| Client API | `/api/client` | `wfmctl bind` | One-shot dynamic client binding. Does not use administrator session token. |
| Internal API | `/api/internal` | EMQX and internal components | Protected by an internal shared key. |
| Dev API | `/api/v0` | Local development and tests | Registered only when `WFM_ENABLE_DEV_TEST_API=true`. |

The MCP HTTP endpoint is `/mcp`, but MCP tools should reuse the same service layer behind the console API.

## Calling Conventions

Console APIs usually use:

```http
Authorization: Bearer <admin-session-token>
```

Setup, login, health checks, and a small number of public endpoints are exceptions. Download endpoints may also accept short-lived file download tokens.

In production, the backend validates public origin and proxied Host. Browser requests must match allowed origins. CLI/curl requests without Origin are accepted only for the primary host. Development mode may relax these checks.

Client artifacts, bulk config packages, and snapshot exports may use 5-minute single-file download tokens. A download token is bound to one resource and cannot call other APIs.

Client download bash commands follow the same boundary. GitHub Release commands download directly from GitHub. Local build commands first ask the backend for `/api/v1/tools/download/client-artifacts/download-grant`, then use the returned single-file token in the copied URL.

Write APIs should follow the same order:

1. Validate input and permissions.
2. Mutate database state in a transaction.
3. Synchronize EMQX or dispatch MQTT if needed.
4. Publish SSE refresh events.
5. Return a result the frontend can show or use to refetch projections.
