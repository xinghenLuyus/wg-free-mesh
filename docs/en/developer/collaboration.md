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

## Image Publishing

The app image is built by GitHub Actions and published to GHCR:

```text
ghcr.io/xinghenluyus/wg-free-mesh-app
```

There is still only one version source: `[project].version` in `src/pyproject.toml`.

Release rules:

- Only `x.y.z` and `x.y.z-rc.n` version formats are supported. Other formats skip image builds.
- The image version tag is read directly from `src/pyproject.toml`, for example `1.0.0` or `1.0.0-rc.1`.
- `dev`, `sha-*`, and other temporary image tags are not published.
- Stable versions also update `latest`.
- RC versions also update `latest` only when the repository has no existing `vX.Y.Z` stable Git tag.
- RC versions do not update `latest` once a stable Git tag exists.
- If the workflow is triggered by a Git tag, the Git tag must be `v<version>`. Mismatches skip image builds.
- Docker compose pulls `latest` by default. Production deployments can pin a version with `WFM_IMAGE_TAG` in `.env`.

After the first publish, confirm that the package is Public in GitHub Packages. Otherwise external users cannot pull it anonymously.

Local Docker build is for development only. Compose keeps the build block commented out and does not use it as the normal deployment path.

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
