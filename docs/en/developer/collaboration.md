# Collaboration

This page defines collaboration rules for developers and automated coding assistants.

Before changing code, start from [Developer Index](./), [Project Structure](./project-structure), and the reference page related to the task.

## Basic Rules

- Read the docs and existing code before deciding how to implement changes.
- The backend is the source of business truth. The frontend displays, accepts input, interacts, and calls APIs.
- Database schema changes require Alembic migrations.
- Changes that affect behavior, APIs, protocols, Docker, data structures, or security must update documentation.
- Do not place temporary files, caches, build outputs, or dependency caches in the workspace.

## Automation Limits

Automated assistants must not independently:

- Start backend, frontend, Docker, EMQX, databases, or the client agent.
- Run build commands.
- Install, upgrade, uninstall dependencies, or change the local environment.
- Work around permission failures.
- Delete data unless explicitly requested.

When permission is insufficient, request elevation and explain why. Do not bypass the issue through temporary scripts or environment changes.

## Documentation Sync

Update docs when changing:

- Feature pages.
- Environment variables.
- Docker compose, Dockerfile, gateway, or reverse proxy behavior.
- API, MCP, MQTT, or SSE protocols.
- Client commands and install behavior.
- Snapshot content and restore semantics.
- Security boundaries.

## Frontend and Backend

If the frontend needs complex derived state, ask the backend for a projection or field. Do not duplicate:

- Online state calculation.
- Mesh topology validation.
- Sync status calculation.
- Artifact cache state.
- EMQX state.

## Git and Workspace

The workspace may contain user changes. Do not revert, overwrite, or clean unrelated files.

Before deleting, moving, or rewriting files, confirm they are part of the current task and will not remove user work.

## Common Entrypoints

- Code boundaries: [Project Structure](./project-structure)
- API behavior: [API Contract](./api-contract) and [API Reference](/en/reference/api)
- MQTT communication: [MQTT Protocol](./mqtt-protocol) and [MQTT Messages](/en/reference/mqtt-messages)
- SSE realtime refresh: [Events](./events) and [Realtime Reference](/en/reference/realtime)
- Data structure: [Database](./database) and [Data Model](/en/reference/data-model)
- Security policy: [Security](/en/reference/security)
