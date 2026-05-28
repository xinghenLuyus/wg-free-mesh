# Backend

The backend uses FastAPI. It provides business APIs, MCP, SSE, snapshots, database access, EMQX synchronization, and client binding.

Before changing backend code, check the dependency direction in [Project Structure](./project-structure). Stable HTTP behavior is defined by [API Contract](./api-contract) and [API Reference](/en/reference/api).

## Main Directories

| Directory | Purpose |
| --- | --- |
| `src/app/api` | HTTP API routers for admin APIs, client APIs, and internal EMQX callbacks. |
| `src/app/core` | Settings, auth, security, and middleware. |
| `src/app/data` | SQLAlchemy schema, database connection, and repository composition. |
| `src/app/domain` | Domain models and protocol parameter generation. |
| `src/app/events` | SSE event publishing. |
| `src/app/infrastructure` | External integrations such as the EMQX management API. |
| `src/app/mcp` | MCP server, resources, tools, permissions, and audit. |
| `src/app/projections` | Page and system status projections. |
| `src/app/services` | Business use cases. |
| `src/app/schemas` | Pydantic request and response models. |

## Layers

Routers handle auth dependencies, request parsing, HTTP boundaries, and calls into services.

Services coordinate business use cases, repositories, events, EMQX, downloads, snapshots, and MCP behavior.

Repositories handle SQL reads, writes, conversion, and transaction boundaries.

Projections build frontend-facing shapes such as home status, config overview, node workspace, and system status.

If a page needs complex derived state, add a backend projection instead of duplicating rules in the frontend.

Typical projections include config overview, mesh workspace, endpoint control status, and system status. For related page behavior, see [Frontend](./frontend), [Events](./events), and [Data Model](/en/reference/data-model).

## State Rule

The database is the source of truth. Runtime state, client state, MQTT credentials, port forwarding rules, MCP tokens, and settings should all be represented in the database.

EMQX is an execution layer. If it is offline, write to the database first and synchronize when it comes back.

When MQTT credentials, online state, or EMQX callbacks change, update [MQTT Protocol](./mqtt-protocol), [MQTT Messages](/en/reference/mqtt-messages), and [Client Lifecycle](/en/reference/client-lifecycle).

## System Update Check

The system status API checks GitHub Releases in the background and adds the result to the `update` field of `/api/v1/system/status`. If the check fails or no newer version exists, the frontend stays silent and does not show an update prompt.

Version selection rules:

- When the current version is stable `x.y.z`, only newer stable releases are considered. RC/snapshot releases are ignored.
- When the current version is an RC/snapshot `x.y.z-rc.n`, newer RC/snapshot releases are considered, and stable releases on the same version line or a newer version line are also considered.
- Results are cached briefly to avoid hitting GitHub on every system status refresh.

System update checking only shows a prompt and links to GitHub Release. The backend never performs self-upgrade.

## Errors

Business errors use the unified error structure. New error codes must be added to [Errors](/en/reference/errors).

Do not expose raw Python, database, or third-party exceptions to the frontend.

## Realtime

After a write operation affects UI state, publish an SSE event. Payloads must be JSON serializable.

Event names, payloads, and frontend refresh rules are covered by [Events](./events) and [Realtime Reference](/en/reference/realtime).

## Tests

Backend tests should cover API behavior, repositories, migrations, snapshots, EMQX offline recovery, MCP permissions, confirmations, and audit.

## Related Docs

- [Project Structure](./project-structure)
- [API Contract](./api-contract)
- [Database](./database)
- [Events](./events)
- [MQTT Protocol](./mqtt-protocol)
- [MCP Reference](/en/reference/mcp)
