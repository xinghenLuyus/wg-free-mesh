# Events

The backend pushes system and business updates to the frontend through SSE. SSE refreshes pages and local state; it does not replace REST APIs.

## Endpoint

```text
GET /api/v1/events/stream
```

The request requires an administrator Bearer token. Production reverse proxies must disable response buffering, otherwise events may be delayed.

For full frame format, event list, and frontend subscription behavior, see [Realtime Reference](/en/reference/realtime).

If an event is triggered by a write API, also check the write order in [API Contract](./api-contract). Frontend consumption rules are in [Frontend](./frontend).

## Event Rules

Event payloads must be JSON serializable. Convert `datetime`, enums, and domain objects to strings or plain objects first.

Events should:

- Tell the page what needs to refresh.
- Keep complex data behind APIs or projections.
- Avoid excessive high-frequency updates.
- Keep event names stable.

## Common Events

| Event | Purpose |
| --- | --- |
| `system.status.updated` | Home, global status, and summary refresh. |
| `config.list.updated` | Config list refresh. |
| `config.overview.updated` | Single config overview refresh. |
| `node.workspace.updated` | Node workspace refresh. |
| `mesh.workspace.updated` | Mesh page refresh. |
| `endpoint.status.updated` | Endpoint control status refresh. |
| `control.log.created` | New control log. |
| `control.log.updated` | Control log status update. |
| `settings.mqtt.updated` | MQTT settings refresh. |
| `snapshot.list.updated` | Snapshot list refresh. |

## Frontend Usage

Treat SSE events as refresh signals:

- Refresh the relevant projection if the current page is affected.
- Append or update log rows for log events.
- Ignore unrelated events.

Do not reimplement backend business derivation from event payloads.

## Publishing

Publish events after database writes complete. Common publishers are config/node/mesh writes, client ACK updates, MQTT setting changes, and snapshot operations.

## Related Docs

- [Realtime Reference](/en/reference/realtime)
- [Frontend](./frontend)
- [Backend](./backend)
- [API Contract](./api-contract)
