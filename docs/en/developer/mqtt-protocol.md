# MQTT Protocol

MQTT is the low-traffic control channel between the backend and clients. It carries online state, config pushes, control commands, detect requests, and ACKs.

If you change topics, payloads, or online-state logic, read [MQTT Messages](/en/reference/mqtt-messages), [Client Lifecycle](/en/reference/client-lifecycle), and [Client](./client) together.

## Roles

| Role | Responsibility |
| --- | --- |
| Backend | Database source of truth, MQTT manager, command publisher, ACK handler. |
| EMQX | MQTT broker plus auth and topic authorization executor. |
| wfm-agent | Client service that subscribes to commands, executes local actions, and reports state. |

The backend always treats the database as truth. When EMQX is online, accounts and authorization are synchronized. When EMQX is offline, data is written first and synchronized later.

## Topic Direction

Topics are isolated by node identity. Clients can only access their own topics. The backend has management and publish permissions.

Typical directions:

- Backend to client: config push, control command, detect.
- Client to backend: heartbeat, info, event, ACK.

See [MQTT Messages](/en/reference/mqtt-messages) for topics, payloads, ACKs, LWT, and online projection. See [Client Lifecycle](/en/reference/client-lifecycle) for the full dynamic node bind and online flow.

## Message Types

Common message types:

- `config/push`: desired config push.
- `control`: start, stop, push_config, wg_show.
- `detect`: client state probing.
- `info`: client version, toolchain, and capabilities.
- `event`: client-initiated event.
- `heartbeat`: low-frequency heartbeat.
- `ack`: command or config result.

## Online State

Online state is not based on a single heartbeat:

- Explicit offline signal always wins.
- Without offline signal, any valid online condition can mark the node online.
- Valid conditions include MQTT connection, control response, detect ACK, and recent status report.

Heartbeat can stay low-frequency to save traffic. MQTT reconnection handles temporary disconnects.

## TLS Boundary

The backend defaults to plain MQTT over the Docker network. Client TLS depends on deployment and bind config.

`WFM_MQTT_TLS_ENABLED` affects the client listener and generated client binding config. It does not force backend-to-EMQX TLS. If `WFM_MQTT_URL` is explicitly set to `mqtts://`, the backend follows that URL.

## Authorization

EMQX calls the backend internal authorization endpoint to validate topic access. The shared secret comes from deployment environment variables.

When a client is reset, the backend deletes or disables the related EMQX user and attempts to disconnect the MQTT session.

The internal callback is listed in [API Reference](/en/reference/api). Security boundaries are in [Security](/en/reference/security), and environment variables are in [Environment Reference](/en/reference/env).

## Related Docs

- [MQTT Messages](/en/reference/mqtt-messages)
- [Client Lifecycle](/en/reference/client-lifecycle)
- [Client](./client)
- [Backend](./backend)
- [Events](./events)
