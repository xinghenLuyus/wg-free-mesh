# Realtime

The console receives realtime updates through SSE. The model is "initial REST snapshot plus SSE refresh signals"; the frontend does not rebuild business truth from SSE alone.

## Endpoint

```http
GET /api/v1/events/stream
Authorization: Bearer <access-token>
```

Response:

```http
Content-Type: text/event-stream
```

Production reverse proxies must disable buffering, for example with Nginx `proxy_buffering off`, or events may not reach the browser immediately.

## Frame Format

Standard SSE frame:

```text
event: system.status.updated
id: evt_xxx
data: {"type":"system.status.updated","payload":{}}
```

| Field | Description |
| --- | --- |
| `event` | Event type. |
| `id` | Event ID. |
| `data` | JSON string containing the event type and payload. |

`data` must be JSON serializable. Convert `datetime` values, enums, and domain objects to strings or plain objects before sending so serialization errors cannot break the SSE stream.

## Connection Strategy

- The frontend maintains one shared SSE connection.
- Pages fetch REST snapshots first, then listen for SSE.
- Page unmount removes listeners but does not close the global connection.
- Reconnect is handled by one shared reconnect layer.
- Backend shutdown wakes subscribers so stream responses exit.

When there are no active subscribers, the server should not keep generating meaningless pushes.

## Initial Events

After connection:

- `system.status.updated`
- `system.clock.sync`

While the connection is alive, `system.clock.sync` is sent periodically, around every 15 seconds. The frontend advances time with a local timer and recalibrates when the next event arrives.

## Events

| Event | Purpose | Typical payload |
| --- | --- | --- |
| `config.list.updated` | Home config cards and sidebar config list. | `configs` |
| `config.overview.updated` | Config overview header, node cards, tags. | `config_id`, `overview`, `tags` |
| `node.workspace.updated` | Node shared header and workspace. | `config_id`, `node_id`, `workspace` |
| `node.apply.updated` | Config preview and sync state. | `config_id`, `node_id`, `sync_status`, `preview`, `applied` |
| `mesh.workspace.updated` | Mesh page workspace. | `config_id`, `node_id`, `workspace`, `nodes` |
| `endpoint.status.updated` | Endpoint control runtime and sync state. | `config_id`, `node_id`, `status` |
| `control.log.created` | New control log. | `config_id`, `node_id`, `log` |
| `control.log.updated` | Control log status update. | `config_id`, `node_id`, `log` |
| `settings.mqtt.updated` | MQTT settings form refresh. | `mqtt` |
| `snapshot.list.updated` | Snapshot list refresh. | `snapshots` |
| `system.status.updated` | Home, system page, global status. | `summary`, `services`, `sync`, `topology`, `update` |
| `system.clock.sync` | Server time sync and SSE liveness. | `timestamp` |

## Mesh Workspace Refresh

Mesh field changes can affect multiple endpoints. When an endpoint public address, listen port, or Mesh pair changes, the backend refreshes not only the current endpoint but also affected peer endpoints through `mesh.workspace.updated`.

`workspace.connections[*]` contains connection-integrity results. The frontend displays broken-link indicators directly instead of deriving topology itself.

## Endpoint Control Refresh

Sources of `endpoint.status.updated` include:

- Passive heartbeat reports.
- Active detect ACK or timeout.
- Info, control, or config-push ACK.
- Client events.
- Client reset.

`info/ack` and `control/ack` update control-log status only. Command output arrives through the MQTT `event`; the backend stores it as a log and then publishes `control.log.created`.

## Frontend Rules

On event:

- If the current page is affected, refetch the relevant projection.
- For log events, append or update rows.
- For system status events, update global status.
- Ignore unrelated events.

Do not duplicate backend online, sync, topology, or artifact state logic in the frontend.

## Backend Publishing

Publish after database writes. Common sources:

- Config, node, tag writes.
- Mesh pair changes.
- Port forwarding changes.
- Sync state changes.
- Client runtime state changes.
- Control log changes.
- MQTT setting changes.
- Snapshot operations.

Mesh changes should also refresh config list and system status so home statistics stay current.
