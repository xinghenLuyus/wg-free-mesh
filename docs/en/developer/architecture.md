# Architecture

WG Free Mesh consists of the web console, backend, database, Go client, EMQX, and Docker gateway. Before changing code, check the component boundaries and version matrix.

## Development Environment

Versions come from the current repository config, lockfiles, and Docker compose files.

| Layer | Component | Current version / constraint | Source |
| --- | --- | --- | --- |
| App version | WG Free Mesh | `1.0.0` | `src/pyproject.toml` |
| Backend runtime | Python | `>=3.12`, Docker image `python:3.12-slim` | `src/pyproject.toml`, `docker/app/backend.Dockerfile` |
| Backend framework | FastAPI | `>=0.115.0` | `src/pyproject.toml` |
| Backend settings | pydantic-settings | `>=2.6.0` | `src/pyproject.toml` |
| Data access | SQLAlchemy | `>=2.0.0` | `src/pyproject.toml` |
| Migrations | Alembic | `>=1.13.0` | `src/pyproject.toml` |
| PostgreSQL driver | psycopg | `>=3.2.0` | `src/pyproject.toml` |
| MQTT client | aiomqtt | `>=2.3.0` | `src/pyproject.toml` |
| MCP server | mcp | `>=1.12.0` | `src/pyproject.toml` |
| Frontend runtime | Node.js | Docker build uses `node:22-alpine` | `docker/app/backend.Dockerfile` |
| Package manager | pnpm | `10.33.0` | `docker/app/backend.Dockerfile` |
| Frontend framework | Vue | `3.5.32` | `front/pnpm-lock.yaml` |
| Frontend build | Vite | `5.4.21` | `front/pnpm-lock.yaml` |
| Frontend language | TypeScript | `5.9.3` | `front/pnpm-lock.yaml` |
| UI components | Element Plus | `2.13.7` | `front/pnpm-lock.yaml` |
| Frontend state | Pinia | `2.3.1` | `front/pnpm-lock.yaml` |
| Frontend router | Vue Router | `4.6.4` | `front/pnpm-lock.yaml` |
| Frontend i18n | vue-i18n | `11.3.2` | `front/pnpm-lock.yaml` |
| HTTP client | Axios | `1.15.0` | `front/pnpm-lock.yaml` |
| Client language | Go | `1.22` | `client/go.mod` |
| Client MQTT | paho.golang | `0.21.0` | `client/go.mod` |
| Documentation | VitePress | `1.6.4` | `docs/package.json` |
| Gateway | Nginx | `1.27-alpine` | `docker/*/docker-compose.yml` |
| MQTT broker | EMQX | `5.8.5` | `docker/*/docker-compose.yml` |
| Production database | PostgreSQL | `16-alpine` | `docker/postgres/docker-compose.yml` |
| Local database | SQLite | Built into Python / SQLAlchemy support | `docker/sqlite/.env.example` |

## Component Topology

```text
Browser / MCP client
  -> Docker gateway (Nginx)
    -> Frontend static files (Vue / Vite)
    -> FastAPI backend
      -> Service layer
      -> SQLAlchemy repositories
      -> SQLite or PostgreSQL
      -> EMQX management API
      -> MCP server
      -> SSE event stream
    -> EMQX MQTT listeners

wfmctl
  -> Backend bind API

wfm-agent
  -> EMQX MQTT
  -> wg / awg / wg-quick / awg-quick
```

## Components

### Web Console

The frontend handles page structure, user input, API calls, state display, and interaction feedback. It does not duplicate backend business rules.

### FastAPI Backend

The backend owns business rules. Configs, nodes, mesh pairs, port forwarding, snapshots, MCP, client binding, MQTT authorization, and system status are driven by application data in the database.

### Database

The database is the business source of truth. SQLite and PostgreSQL are both supported through SQLAlchemy. Schema changes must go through Alembic migrations.

### EMQX

EMQX is the MQTT transport layer. Node accounts, passwords, authorization rules, and connection state are synchronized by the backend from the database.

### Go Client

The client consists of `wfm-agent` and `wfmctl`. `wfm-agent` runs as a system service. `wfmctl` installs, binds, checks status, reads logs, starts, stops, and uninstalls the service.

### Docker Gateway

Docker deployment provides one web entrypoint through the gateway. Production HTTPS should be terminated by Nginx, Caddy, or an external gateway.

## Control Plane and Data Plane

WFM manages the WireGuard / AmneziaWG control plane. It does not proxy tunnel traffic.

Control plane:

- Browser console.
- REST API calls to the backend.
- SSE events from backend to console.
- MQTT commands from backend to dynamic clients through EMQX.
- MQTT heartbeat, ACK, runtime status, and logs from clients.
- MCP calls through `/mcp`.

Data plane:

- WireGuard / AmneziaWG UDP tunnels between nodes.
- User traffic inside those tunnels.
- Port forwarding rules applied locally on the destination node through lifecycle hooks.

The backend is not in the mesh data path. If the backend is offline, already-running tunnels may keep running with their local client config, but the console cannot push new config or commands.

## Entrypoints

| Entrypoint | Consumer | Notes |
| --- | --- | --- |
| Web/API/SSE/MCP gateway | Browser, AI clients, external HTTP callers | Docker deployment exposes these through the gateway. |
| MQTT public listener | `wfm-agent` | Clients connect to EMQX. Port and TLS depend on deployment and settings. |
| WG/AWG UDP | Mesh nodes | Direct node-to-node data traffic; not proxied by WFM. |

Production deployments should put Web/API/SSE/MCP behind the same HTTPS reverse proxy entrypoint. MQTT may be exposed by the gateway on separate ports.

## Client Channel

A dynamic node uses two channels:

1. One-shot HTTP bind: `wfmctl bind` calls `/api/client/bind` with a bind token.
2. Long-running MQTT control channel: `wfm-agent` connects to EMQX using credentials returned by bind.

After bind, the backend stores MQTT credentials in the database and synchronizes them to EMQX. The local client profile stores only connection data. The backend includes the current tunnel protocol and config in each control, detect, and config push payload.

## Realtime Channel

The console uses SSE instead of WebSocket because writes already go through REST, while realtime mainly needs server-to-browser refresh signals.

SSE events are refresh hints. The frontend should use event type and scope to refetch the related REST projection instead of reconstructing business state from event payloads.

## EMQX Sync Model

EMQX is a runtime projection, not the business source of truth.

The backend:

- Generates node MQTT username/password/client_id.
- Stores them in the database.
- Creates or updates EMQX users through the management API.
- Serves EMQX AuthZ HTTP callbacks.
- Rebuilds EMQX node users after backend startup, EMQX recovery, and snapshot restore.

If EMQX is temporarily unavailable, the backend should still start and non-MQTT features should keep working. Client control features should report unavailable instead of bringing down the whole application.

## Snapshot Model

Snapshots are application-level snapshots, not raw database file copies.

They include application data except the administrator password, including configs, nodes, mesh links, port forwards, system settings, MCP tokens, MCP audit records, client MQTT credentials, snapshot metadata, and WireGuard directory data.

After restore, historical online state is not trusted. The backend clears runtime state, rebuilds EMQX users from restored client credentials, and uses detect to confirm endpoint state again.

## Failure Behavior

| Failure | Expected behavior |
| --- | --- |
| EMQX unavailable | Backend can start; MQTT control is unavailable; database remains the source of truth. |
| Client offline | Control commands cannot complete; UI shows offline or dropped; runtime state waits for client report. |
| SSE disconnected | Frontend reconnects and may refetch system status. |
| Database unavailable | Backend startup fails after retry; it must not fabricate business state. |
| Gateway unavailable | External Web/API/SSE/MCP access fails even if internal services are running. |

## Write Flow

1. The frontend calls a backend API.
2. The backend validates and writes to the database.
3. The backend publishes SSE events.
4. If a client action is needed, the backend sends MQTT commands.
5. Client ACKs update runtime state and control logs.

## Design Decisions

- The backend should still start when EMQX is temporarily unavailable.
- Snapshots are application-level data, not SQLite files or PostgreSQL dumps.
- MCP and Web APIs reuse the same business layer.
- Docker is the recommended deployment path because it coordinates backend, frontend, EMQX, certificates, and gateway behavior.

## Continue Reading

- Source directories and ownership boundaries: [Project Structure](./project-structure).
- Backend services and repositories: [Backend](./backend).
- Migrations, repositories, and snapshots: [Database](./database).
- Dynamic client communication: [MQTT Protocol](./mqtt-protocol) and [Client Lifecycle](/en/reference/client-lifecycle).
- Browser realtime refresh: [Events](./events) and [Realtime Reference](/en/reference/realtime).
- Deployment, environment variables, and HTTPS reverse proxy: [Docker Deploy](/en/deploy/), [Environment](/en/deploy/environment), [Reverse Proxy](/en/deploy/reverse-proxy).
