# Frontend

The frontend uses Vue 3, Vite, TypeScript, Pinia, Vue Router, and Element Plus.

Before frontend work, read the frontend boundary in [Project Structure](./project-structure). If a page needs cross-resource derived state, prefer adding a backend projection in [Backend](./backend).

## Main Directories

| Directory | Purpose |
| --- | --- |
| `front/src/views` | Page views. |
| `front/src/components` | Reusable components. |
| `front/src/api` | API client wrappers. |
| `front/src/stores` | Pinia stores. |
| `front/src/router` | Route definitions. |
| `front/src/i18n` | Chinese and English messages. |
| `front/src/types` | Frontend API types. |
| `front/src/composables` | Shared Composition API logic. |

## Core Rule

The frontend displays, accepts input, handles interactions, and calls APIs. It should not reimplement:

- Node online calculation.
- Sync status calculation.
- Mesh topology validation.
- Artifact cache state.
- Snapshot parsing.
- EMQX status derivation.
- MCP permission decisions.

Ask the backend for fields or projections when a page needs derived state.

Stable fields and errors are documented in [API Reference](/en/reference/api), [Data Model](/en/reference/data-model), and [Errors](/en/reference/errors).

## Pages

Major page groups:

- Home: system overview and config entrypoints.
- Config overview: configs, nodes, tags, and basic state.
- Node workspace: mesh, sync, control, and advanced settings.
- Tools: downloads, quick mesh, port forwarding, AI integration.
- Settings: system settings, MQTT, backups, and password.
- Help entry: the sidebar opens the public documentation site in a new tab; there is no local Help page.

Tool pages should focus on user actions and avoid exposing backend cache paths or temporary internals.

Tool-page behavior links to [Downloads](/en/reference/downloads), [Quick Mesh](/en/reference/quick-mesh), [MCP Reference](/en/reference/mcp), and [Snapshots](/en/reference/snapshot).

## Realtime

The frontend receives SSE events. Treat them as refresh signals or small patches, not as the business source of truth.

The full event list, scopes, and subscription strategy are in [Realtime Reference](/en/reference/realtime).

## i18n

All visible text belongs in `front/src/i18n/messages`. Add Chinese and English messages together.

Use stable backend error codes for localized errors.

## UX Direction

This is an operations console. Prefer dense, scannable, task-oriented UI:

- Important actions stay close to context.
- Bulk and dangerous operations need clear prompts.
- Long operations block duplicate submissions.
- Mobile layouts must not overlap text or controls.

## Related Docs

- [Backend](./backend)
- [API Contract](./api-contract)
- [Events](./events)
- [Auth](/en/reference/auth)
- [Security](/en/reference/security)
