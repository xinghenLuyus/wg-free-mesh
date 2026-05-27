# Project Structure and Boundaries

This page explains where code lives, which layer owns which responsibility, and where a change should land.

## Root Layout

```text
wg-free-mesh/
  src/       FastAPI backend, migrations, backend tests
  front/     Vue console
  client/    Go client and CLI
  docker/    Docker deployment, gateway, EMQX config
  docs/      VitePress documentation site
  docs-bak/  archived old docs, used only as migration reference
```

Business code should live only in `src/`, `front/`, `client/`, `docker/`, and `docs/`. Do not place new runtime modules, temporary caches, build outputs, or runtime data in the repository root.

If you have not read the system topology yet, start with [Architecture](./architecture). This page focuses on directories and change placement.

## Backend

```text
src/
  pyproject.toml
  alembic.ini
  migrations/
  app/
    main.py
    api/
      client/
      internal/
      v1/
    core/
    data/
    domain/
    events/
    infrastructure/
    mcp/
    projections/
    schemas/
    services/
  tests/
```

| Directory | Boundary |
| --- | --- |
| `api/v1` | Admin REST API. Authentication dependencies, request parsing, response wrapping, and HTTP errors only. |
| `api/client` | Client bind entrypoint for `wfmctl bind`; not a console API. |
| `api/internal` | Internal callbacks such as EMQX AuthZ. Protected by internal shared key. |
| `core` | Config, auth, security, public host/origin checks, base errors. |
| `data` | SQLAlchemy engine, schema, repositories, transactions, and data access composition. |
| `domain` | Domain enums, protocol parameter generation, and pure rules without IO. |
| `events` | SSE event publishing and subscriber management. |
| `infrastructure` | External adapters such as EMQX management API. |
| `mcp` | MCP server, resources, tools, permissions, confirmation, and audit. |
| `projections` | Read models for pages such as config overview, mesh workspace, and system status. |
| `schemas` | Pydantic request and response models. |
| `services` | Application use cases and business orchestration. |
| `tests` | Backend tests. Temporary test data must use system temp paths or test-specific folders, not workspace root. |

For backend layering, continue with [Backend](./backend). For stable interface behavior, read [API Contract](./api-contract) and [API Reference](/en/reference/api).

## Backend Dependency Direction

Preferred direction:

```text
api -> services -> data
api -> services -> infrastructure
api -> services -> events
mcp -> services
projections -> data
services -> projections
```

Avoid:

- Routes writing SQL directly.
- Frontend assembling cross-resource business rules from multiple APIs.
- MCP tools bypassing services and mutating repositories directly.
- Repositories calling HTTP, EMQX, SSE, or MCP.
- Domain code reading environment variables, databases, or networks.

## Frontend

```text
front/
  src/
    api/
    assets/
    components/
    router/
    stores/
    types/
    views/
```

| Directory | Boundary |
| --- | --- |
| `views` | Page-level components and page interactions. |
| `components` | Reusable UI components; no cross-resource business rules. |
| `router` | Routes and navigation guards. |
| `stores` | Pinia state such as auth, layout, and preferences. |
| `api` | HTTP client wrappers and API functions. |
| `types` | Frontend type definitions aligned with backend responses. |
| `assets` | Global styles, theme variables, and asset references. |

The frontend may handle layout, local interaction, lightweight input validation, REST calls, SSE subscriptions, and display of backend projections.

The frontend should not generate WG/AWG configs, decide final online state, validate mesh topology, compute quick-mesh output, compute default AllowedIPs, track backend build artifacts, or implement MCP/control business rules outside the backend.

For page organization, SSE usage, and i18n rules, continue with [Frontend](./frontend).

## Client

```text
client/
  cmd/
    agent/
    ctl/
  internal/
    agent/
    bind/
    config/
    control/
    mqtt/
    profile/
    service/
```

The client has two executables:

- `wfm-agent`: system service for MQTT sessions, config push, control commands, status reports, and logs.
- `wfmctl`: CLI for install, uninstall, bind, start/stop, status, and logs.

The client is not the business source of truth. It stores local profiles, local service state, and recent execution output. Tunnel protocol, AWG parameters, and control actions should come from the backend payload sent for the current operation.

For the client runtime model, continue with [Client](./client). For full MQTT topics and payloads, see [MQTT Messages](/en/reference/mqtt-messages).

## Docker

```text
docker/
  app/
  emqx/
  gateway/
  sqlite/
  postgres/
```

| Directory | Boundary |
| --- | --- |
| `sqlite` | SQLite deployment entrypoint for personal and small setups. |
| `postgres` | PostgreSQL deployment entrypoint for long-running and higher-volume setups. |
| `app` | Application image build context. |
| `gateway` | Nginx gateway template for Web/API/SSE/MCP and MQTT public ports. |
| `emqx` | EMQX config templates, startup script, and certificate generation. |

Docker is the recommended deployment path because WFM includes more than a Web app: backend, frontend, EMQX, gateway, certificates, database, and background reconciliation.

Deployment steps live in [Docker Deploy](/en/deploy/). Environment fields live in [Environment Reference](/en/reference/env).

## Data Directory

Runtime data defaults to `src/data`. Docker deployments mount it into the app container. It may contain:

- SQLite database or app data files.
- WireGuard / AmneziaWG generated configs.
- Snapshots.
- Client build artifacts.
- Bulk config download packages.

This is runtime data, not source code. Documentation, tests, and dev scripts must not depend on a specific local file existing there.

## Source of Truth

The database is the source of truth:

- Configs, nodes, mesh links, port forwards, system settings, MCP tokens, MCP audit, and client MQTT credentials are database data.
- EMQX is a runtime projection of database state.
- Client profiles are local copies of backend-dispatched state.
- SSE is a refresh signal, not a source of truth.
- Frontend stores are display caches, not business truth.

## Where Changes Land

| Requirement | Preferred landing area |
| --- | --- |
| New business field | `data` schema + Alembic + repository + schema + service + docs |
| New page display field | Prefer `projections`; frontend consumes the projection |
| New console API | `schemas` + `services` + `api/v1` + `reference/api` |
| New MCP capability | Reuse `services` + `mcp/tools` + `mcp/resources` + MCP docs |
| New client command | `client/cmd/ctl` + `client/internal` + client docs |
| MQTT topic or payload change | Backend MQTT service + Go client + MQTT reference + client lifecycle docs |
| Database schema change | Alembic migration + SQLAlchemy schema + snapshot tests |
| Docker behavior change | `docker/*` + environment docs + deployment docs |

## Documentation Placement

- User workflows: `guide/` or `usage/`.
- Stable fields, APIs, protocols, errors: `reference/`.
- Code structure, architecture, implementation boundaries: `developer/`.

Do not turn temporary plans, development notes, or AI collaboration traces into user-facing documentation. User docs should describe the current system behavior.

## Related Docs

- [Architecture](./architecture)
- [Backend](./backend)
- [Frontend](./frontend)
- [Client](./client)
- [Database](./database)
- [Collaboration](./collaboration)
