# API Reference

The REST API primarily uses `/api/v1` and returns successful responses in this form:

```json
{
  "success": true,
  "data": {}
}
```

Error responses use this form:

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

## API Layers

WFM exposes four HTTP API layers rather than a single browser API:

| Layer | Prefix | Caller | Notes |
| --- | --- | --- | --- |
| Console API | `/api/v1` | Browser console and trusted external callers | Main business API. Requires an administrator Bearer token by default. |
| Client API | `/api/client` | `wfmctl bind` | Used only for one-time client binding and does not use the administrator session token. |
| Internal API | `/api/internal` | EMQX and other internal components | Intended for containers or trusted networks and requires an internal shared key. |
| Dev API | `/api/v0` | Local development and automated tests | Registered only when `WFM_ENABLE_DEV_TEST_API=true`. |

The MCP HTTP endpoint is `/mcp`. MCP tools must reuse the same service logic behind the console API rather than bypassing the business layer.

## Calling Conventions

### Administrator Session

Console business APIs normally use:

```http
Authorization: Bearer <admin-session-token>
```

Login, setup, health checks, and a small number of other endpoints allow anonymous access. Download endpoints may also accept download-specific tokens.

### Source Restrictions

In production, the backend validates the configured public origin and the proxied Host. Browser requests must come from an allowed origin; CLI and curl requests without an Origin are accepted only for the primary Host. Development mode may relax these checks.

### Download Tokens

Client artifacts, bulk config packages, and snapshot exports can use five-minute single-file download tokens. A token can access only its bound resource and cannot call other APIs or download another file.

### Business Writes

Write endpoints follow the same order:

1. Validate input and permissions.
2. Mutate business data inside a database transaction.
3. Synchronize EMQX or dispatch MQTT when required.
4. Publish SSE refresh events.
5. Return a result that the frontend can display or use to refresh projections.

When an external system is unavailable, database semantics should remain explicit: persist operations that are safe to persist, and return a clear business error when consistency cannot be guaranteed.

## Authentication API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/auth/state` | Read setup and current-session state. |
| `POST` | `/api/v1/auth/setup` | Initialize the administrator password. |
| `POST` | `/api/v1/auth/login` | Sign in and return a Bearer token. |
| `GET` | `/api/v1/auth/session` | Validate the current Bearer token. |
| `POST` | `/api/v1/auth/logout` | Frontend logout endpoint. |
| `POST` | `/api/v1/auth/password` | Change the administrator password. |

## Config API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/configs` | List configs. |
| `POST` | `/api/v1/configs` | Create a config. |
| `GET` | `/api/v1/configs/{config_id}` | Read a config. |
| `PUT` | `/api/v1/configs/{config_id}` | Update a config. |
| `DELETE` | `/api/v1/configs/{config_id}` | Delete a config. |
| `GET` | `/api/v1/configs/{config_id}/overview` | Read the config overview projection. |
| `POST` | `/api/v1/configs/awg/random` | Generate config-level AmneziaWG parameters. |
| `POST` | `/api/v1/configs/awg/generate` | Generate shared and endpoint drafts without database access or MQTT. |
| `GET` | `/api/v1/configs/protocol-options` | Read AWG versions, the default version, and per-version parameter capabilities. |
| `POST` | `/api/v1/configs/awg/convert` | Prefill an AWG draft for the target version; extensions include only supported fields and randomization strategy, without database writes. |

AWG config writes use `tunnel_protocol=amneziawg` and `awg_version=1.5/2.0/3.1`. Selecting AWG for the first time requires a version. The API also accepts `tunnel_protocol=amneziawg_2`, parsed as AWG 2.0. Config and endpoint extensions use `awg_options`. Conversion accepts current parameters, `source_version` (nullable), and the target `awg_version`. Config update responses include `adjustments` describing backend-adjusted fields.

Config-level and endpoint-level `/awg/random` endpoints accept an `awg_version` query parameter, defaulting to 2.0. Config randomization normally generates S/H only; `regenerate_key=true` generates the shared 3.1 key separately. MCP writes follow the same version and parameter rules.

Unified generation uses `POST /configs/awg/generate` with `awg_version`, `direction` (`generic/dns/stun/rtp/quic`), `intensity` (`low/balanced/high`), current `config` parameters, and `nodes` (endpoint ID → current AWG parameters). It returns `{config, nodes}` for editing only. Config updates accept `awg_node_updates` (endpoint ID → J/I and awg_options), written atomically with shared parameters. IDs outside the config and non-AWG endpoint fields are rejected. Cleared I values are omitted, not randomly refilled. The frontend discards unsaved endpoint drafts when changing version. Pages use this endpoint for random generation.

## Endpoint API

The generation endpoint also accepts `scope=node` (default `all`), requiring exactly one endpoint in `nodes`. Existing shared parameters are validated without generating S/H, shared keys, or changing mechanism switches. Response `config` only echoes validated shared parameters. The endpoint page uses only the returned node draft and saves through `PUT /api/v1/nodes/{node_id}`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/nodes` | List endpoints in a config. |
| `POST` | `/api/v1/configs/{config_id}/nodes` | Create an endpoint. |
| `GET` | `/api/v1/nodes/{node_id}` | Read an endpoint. |
| `PUT` | `/api/v1/nodes/{node_id}` | Update an endpoint. |
| `DELETE` | `/api/v1/nodes/{node_id}` | Delete an endpoint. |
| `POST` | `/api/v1/configs/{config_id}/nodes/suggest-ip` | Suggest a virtual IP. |
| `POST` | `/api/v1/configs/{config_id}/nodes/validate-ip` | Validate a virtual IP. |
| `POST` | `/api/v1/nodes/keys/generate` | Generate a WireGuard key pair. |
| `POST` | `/api/v1/nodes/keys/derive-public` | Derive a public key from a private key. |
| `POST` | `/api/v1/nodes/awg/random` | Generate endpoint-level AmneziaWG parameters. |

## Tag API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/tags` | List tags and counts. |
| `POST` | `/api/v1/configs/{config_id}/tags` | Create a tag. |
| `POST` | `/api/v1/configs/{config_id}/tags/apply` | Apply a tag to multiple endpoints. |
| `DELETE` | `/api/v1/configs/{config_id}/tags/{tag_name}` | Delete a config-level tag. |
| `PUT` | `/api/v1/nodes/{node_id}/tags` | Replace endpoint tags. |
| `DELETE` | `/api/v1/nodes/{node_id}/tags/{tag_name}` | Remove a tag from an endpoint. |

## Mesh API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/peer-links` | List Mesh pairs. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/mesh-workspace` | Read an endpoint Mesh workspace. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/peer-link-draft` | Build a Mesh pair draft. |
| `POST` | `/api/v1/configs/{config_id}/peer-links` | Create a bidirectional Mesh pair. |
| `PUT` | `/api/v1/peer-links/{group_id}` | Update a bidirectional Mesh pair. |
| `DELETE` | `/api/v1/peer-links/{group_id}` | Delete a bidirectional Mesh pair. |
| `POST` | `/api/v1/peer-links/psk/generate` | Generate a PSK. |
| `POST` | `/api/v1/configs/{config_id}/mesh/validate` | Validate the Mesh topology. |
| `POST` | `/api/v1/configs/{config_id}/mesh/quick-generate` | Delete and regenerate Mesh pairs using Quick Mesh. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/wg-preview` | Preview the generated WG/AWG config. |

When updating a Mesh pair, `forward` and `reverse` are matched to existing records by their `local_node_id` and `peer_node_id`, so either endpoint can edit the pair. The two directions must be opposites and refer to the existing pair's endpoints; otherwise, the API returns `INVALID_PEER_LINK`.

## Config Apply and Endpoint Control API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/configs/{config_id}/sync-status` | Read sync states for all endpoints in a config. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/sync-status` | Read one endpoint sync state. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/applied-conf` | Read applied config text. |
| `PUT` | `/api/v1/configs/{config_id}/nodes/{node_id}/applied-conf` | Save applied config text. |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/sync` | Sync one endpoint. |
| `POST` | `/api/v1/configs/{config_id}/sync-all` | Sync all eligible endpoints in a config. |
| `GET` | `/api/v1/configs/{config_id}/endpoint/runtime-snapshot` | Read the runtime snapshot. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint/status` | Read endpoint runtime status. |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/bind-command` | Create a client bind command. |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/reset-client` | Reset client binding and MQTT credentials. |
| `GET` | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint/logs` | Read endpoint control logs. |
| `POST` | `/api/v1/configs/{config_id}/nodes/{node_id}/endpoint/control` | Send `start`, `stop`, `push_config`, or `wg_show`. |
| `POST` | `/api/v1/configs/{config_id}/endpoint/probe-batch` | Probe endpoints in a batch. |

## Tools API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/tools/download/client-options` | Read client build options. |
| `POST` | `/api/v1/tools/download/client-artifacts/build` | Build or locate a client artifact. |
| `POST` | `/api/v1/tools/download/client-artifacts/download-grant` | Create a five-minute single-file token for a local-build client artifact; Release artifacts do not use this endpoint. |
| `GET` | `/api/v1/tools/download/client-artifacts/{artifact_id}` | Download a client artifact. |
| `GET` | `/api/v1/tools/download/config-bulk/options` | Read bulk config download options. |
| `POST` | `/api/v1/tools/download/config-bulk/package` | Create a bulk config package. |
| `GET` | `/api/v1/tools/download/config-bulk/package/{package_id}` | Download a bulk config package. |
| `GET` | `/api/v1/tools/port-forwards/configs/{config_id}` | List port-forward rules. |
| `POST` | `/api/v1/tools/port-forwards/configs/{config_id}` | Create a port-forward rule. |
| `PUT` | `/api/v1/tools/port-forwards/{rule_id}/enabled` | Enable or disable a port-forward rule. |
| `DELETE` | `/api/v1/tools/port-forwards/{rule_id}` | Delete a port-forward rule. |

## Backup API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/backups/snapshot` | Create a snapshot. |
| `GET` | `/api/v1/backups/list` | List snapshots. |
| `GET` | `/api/v1/backups/download/{snapshot_id}` | Download a snapshot. |
| `GET` | `/api/v1/backups/export/{snapshot_id}` | Export a snapshot. |
| `POST` | `/api/v1/backups/restore/{snapshot_id}` | Restore a snapshot. |
| `POST` | `/api/v1/backups/upload` | Upload and import a snapshot. |
| `POST` | `/api/v1/backups/import` | Upload and import a snapshot. |
| `DELETE` | `/api/v1/backups/{snapshot_id}` | Delete a snapshot. |
| `PUT` | `/api/v1/backups/{snapshot_id}/note` | Update a snapshot note. |

## Settings and System API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/settings/ui` | Read UI settings. |
| `PUT` | `/api/v1/settings/ui` | Update UI settings. |
| `GET` | `/api/v1/settings/mqtt` | Read the client-facing MQTT address. |
| `PUT` | `/api/v1/settings/mqtt` | Update the client-facing MQTT address. |
| `POST` | `/api/v1/settings/mqtt/reset` | Reset MQTT settings to environment defaults. |
| `POST` | `/api/v1/settings/mqtt/test` | Test MQTT access settings. |
| `POST` | `/api/v1/settings/password` | Change the administrator password. |
| `GET` | `/api/v1/system/health` | Health check. |
| `GET` | `/api/v1/system/timezone` | Read the configured timezone. |
| `GET` | `/api/v1/system/status` | Read system status. |
| `GET` | `/api/v1/events/stream` | SSE realtime event stream. |

## Client and Internal API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/client/bind` | Exchange a bind token for a profile, MQTT credentials, and config. |
| `POST` | `/api/internal/emqx/authz` | Internal-only EMQX HTTP AuthZ callback. |
| `POST` | `/api/v0/dev/reset-bootstrap` | Dev/test endpoint registered only when `WFM_ENABLE_DEV_TEST_API=true`. |
