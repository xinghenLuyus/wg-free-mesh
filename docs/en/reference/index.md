# Reference

Reference pages document stable APIs, protocol fields, errors, and security boundaries. This section is a factual manual for system behavior, not a tutorial.

## Access and interfaces

- [Auth](./auth): admin sessions, download tokens, MCP tokens, and source guard rules.
- [API](./api): REST APIs, client binding, internal EMQX callbacks, and development endpoints.
- [Realtime](./realtime): SSE stream, event frame format, and frontend subscription behavior.
- [MCP](./mcp): MCP resources, tools, write confirmations, and audit behavior.

## Protocols and data

- [MQTT Messages](./mqtt-messages): client status, control commands, ACKs, and topic authorization.
- [Client Lifecycle](./client-lifecycle): dynamic node binding, online state, disconnects, reset, and page transitions.
- [Downloads](./downloads): client artifacts, config packages, snapshot exports, and short-lived URLs.
- [Snapshots](./snapshot): application-level snapshot contents, encryption, and restore boundaries.
- [Data Model](./data-model): configs, nodes, peer links, runtime state, and sync state.
- [Protocols](./protocols): WireGuard, AmneziaWG 2.0, and AWG parameter rules.
- [Quick Mesh](./quick-mesh): gateway, full mesh, and Free Mesh generation rules.

## Runtime boundaries

- [Security](./security): public source guard, MCP boundaries, high-risk operations, and data protection.
- [Environment](./env): deployment environment variables.
- [Errors](./errors): unified error responses and common business error codes.
