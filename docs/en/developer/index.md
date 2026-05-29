# Developer

These pages are for maintainers and contributors. They explain WG Free Mesh internals, module boundaries, and collaboration rules.

If you only want to deploy and use the system, start with [Guide](/en/guide/) and [Usage](/en/usage/). Read this section before changing the backend, frontend, client, database schema, MQTT protocol, or MCP capabilities.

## Reading Order

1. [Architecture](./architecture): understand the main processes and components.
2. [Development Startup](./dev-start): start the local development environment in EMQX, backend, frontend order.
3. [Project Structure](./project-structure): understand source directories, runtime data, and ownership boundaries.
4. [Backend](./backend): understand where business rules live.
5. [Database](./database): understand SQLAlchemy, Alembic, and snapshots.
6. [Frontend](./frontend): understand why the frontend does not duplicate backend rules.
7. [Client](./client): understand `wfm-agent` and `wfmctl`.
8. [Events](./events): understand SSE event boundaries.
9. [MQTT Protocol](./mqtt-protocol): understand the control channel between backend, EMQX, and clients.
10. [API Contract](./api-contract): understand response shape, errors, and download tokens.
11. [Collaboration](./collaboration): read this before making broad changes.

## By Task

| Task | Start with | Then check |
| --- | --- | --- |
| Add a console page | [Frontend](./frontend) | [Backend](./backend), [API Reference](/en/reference/api), [Realtime Reference](/en/reference/realtime) |
| Add or change a backend API | [API Contract](./api-contract) | [Backend](./backend), [Errors](/en/reference/errors), [MCP Reference](/en/reference/mcp) |
| Change database fields or tables | [Database](./database) | [Data Model](/en/reference/data-model), [Snapshots](/en/reference/snapshot) |
| Change dynamic client control | [Client](./client) | [MQTT Protocol](./mqtt-protocol), [MQTT Messages](/en/reference/mqtt-messages), [Client Lifecycle](/en/reference/client-lifecycle) |
| Change mesh generation or AllowedIPs | [Backend](./backend) | [Quick Mesh Reference](/en/reference/quick-mesh), [Data Model](/en/reference/data-model) |
| Change WireGuard / AmneziaWG parameters | [Client](./client) | [Protocols](/en/reference/protocols), [MQTT Messages](/en/reference/mqtt-messages) |
| Change MCP capabilities | [API Contract](./api-contract) | [MCP Reference](/en/reference/mcp), [Security](/en/reference/security) |
| Change deployment or environment variables | [Architecture](./architecture) | [Environment](/en/reference/env), [Docker Deploy](/en/deploy/), [Reverse Proxy](/en/deploy/reverse-proxy) |

## Before Changing Code

The core rule is simple: the backend and database are the source of truth. The frontend displays and calls. The client executes local actions.

Update documentation when changing:

- API paths, request fields, response fields, or error codes.
- Database tables, migrations, or snapshot content.
- MQTT topics, payloads, ACKs, or online state rules.
- MCP resources, tools, permissions, or audit behavior.
- Docker, environment variables, reverse proxy, or deployment layout.
- Client commands, install behavior, or local file layout.
