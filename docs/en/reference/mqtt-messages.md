# MQTT Messages

This page defines MQTT topics, message envelopes, message types, ACK rules, and online-state projection between the backend and `wfm-agent`.

MQTT is only the low-traffic control channel. The database remains the source of business truth, and EMQX is the transport executor.

## Enable and Disable

When `WFM_ENABLE_MQTT_SERVICES=false`:

- Client binding is unavailable.
- Endpoint control is unavailable.
- MQTT-related dynamic endpoint APIs return `MQTT_DISABLED`.
- The frontend should hide or disable endpoint control.
- The backend must not depend on EMQX to start.

When MQTT is enabled, Docker starts EMQX through `COMPOSE_PROFILES=mqtt`. The backend synchronizes accounts, authorization, and client state after EMQX is online.

## Connection Boundary

The backend connects through `WFM_MQTT_URL`, defaulting to Docker-internal plain MQTT:

```text
mqtt://emqx:1883
```

Client TLS is controlled by deployment and bind config. `WFM_MQTT_TLS_ENABLED=true` enables the client TLS listener and makes generated bind configs prefer TLS. It does not force backend-to-EMQX TLS.

## Client Bind Profile

After `wfmctl bind`, the client receives:

- `config_id`
- `node_id`
- `server_url`
- `mqtt.host`
- `mqtt.port`
- `mqtt.tls`
- `mqtt.username`
- `mqtt.password`
- `mqtt.client_id`
- `topics`
- TLS CA when `tls=true`

Tunnel protocol is not stored in the bind profile. Every command, config push, and detect payload carries `tunnel_protocol`; the client must use the value from the current message.

## Topics

All topics are scoped by `config_id + node_id`.

Downstream:

| Topic | Direction | Purpose |
| --- | --- | --- |
| `wfm/{config_id}/{node_id}/config/push` | Backend -> client | Push current node config. |
| `wfm/{config_id}/{node_id}/control` | Backend -> client | Start, stop, push config, show status. |
| `wfm/{config_id}/{node_id}/detect` | Backend -> client | Probe client state. |
| `wfm/{config_id}/{node_id}/info` | Backend -> client | Request diagnostics. |

Upstream:

| Topic | Direction | Purpose |
| --- | --- | --- |
| `wfm/{config_id}/{node_id}/config/push/ack` | Client -> backend | Config push ACK. |
| `wfm/{config_id}/{node_id}/control/ack` | Client -> backend | Control command ACK. |
| `wfm/{config_id}/{node_id}/detect/ack` | Client -> backend | Detect ACK. |
| `wfm/{config_id}/{node_id}/info/ack` | Client -> backend | Info completion ACK. |
| `wfm/{config_id}/{node_id}/event` | Client -> backend | Client events and command output. |
| `wfm/{config_id}/{node_id}/heartbeat` | Client -> backend | Low-frequency heartbeat. |

Rules:

- Clients can only subscribe to their own downstream topics.
- Clients can only publish to their own upstream topics.
- The backend high-privilege MQTT client subscribes to all upstream topics.
- Clients must not receive wildcard authorization such as `wfm/#` or `wfm/+`.

## Envelope

All messages use JSON:

```json
{
  "type": "heartbeat",
  "request_id": "",
  "config_id": "cfg_xxx",
  "node_id": "node_xxx",
  "boot_id": "boot_uuid",
  "session_id": "session_uuid",
  "sent_at": "2026-04-23T12:00:00Z",
  "payload": {}
}
```

`request_id` is required for command-like messages and empty for passive messages.

## Config Push

Topic:

```text
wfm/{config_id}/{node_id}/config/push
```

ACK:

```text
wfm/{config_id}/{node_id}/config/push/ack
```

Payload:

```json
{
  "action": "push_config",
  "tunnel_protocol": "wireguard",
  "interface_name": "mesh-main-node-a",
  "config_version": 3,
  "config_sha256": "abc...",
  "config_text": "[Interface]\n..."
}
```

If the profile interface is running, the client stops it, writes config, and starts it again. `applied` means the whole flow succeeded. If the interface is not running, the client writes config only.

## Control

Topic:

```text
wfm/{config_id}/{node_id}/control
```

ACK:

```text
wfm/{config_id}/{node_id}/control/ack
```

Actions:

| action | Purpose |
| --- | --- |
| `start` | Start current profile interface. |
| `stop` | Stop current profile interface. |
| `push_config` | Trigger config push flow. |
| `wg_show` | Request `wg` or `awg` diagnostics. |

The payload must include `tunnel_protocol` and `interface_name`. The client must only operate the current profile interface.

`wg_show` command output is sent through `event`, not ACK.

## Detect

Detect probes comprehensive client state. It is sent only when there are active frontend SSE subscribers.

ACK payload:

```json
{
  "status": "applied",
  "client_online": true,
  "wg_online": true,
  "platform": "windows",
  "client_version": "0.2.3",
  "message": "Detect completed"
}
```

`wg_online` only means the current profile interface state.

## Info

`info` requests diagnostics. `info/ack` only marks completion; stdout and stderr are sent through `event`.

## Event

Topic:

```text
wfm/{config_id}/{node_id}/event
```

Event payload:

```json
{
  "level": "info",
  "event": "mqtt_connected",
  "message": "MQTT session established."
}
```

Command output payload:

```json
{
  "level": "info",
  "event": "command_output",
  "request_id": "req_xxx",
  "action": "wg_show",
  "stream": "stdout",
  "message": "wg completed.",
  "output": "interface: wg0\n..."
}
```

Events do not need ACK. Non-offline events count as reachable signals.

## ACK

ACK is required for:

- `config/push`
- `control`
- `detect`
- `info`

ACK is not required for:

- `event`
- `heartbeat`

Statuses:

| status | Meaning |
| --- | --- |
| `accepted` | Received or queued. |
| `applied` | Completed successfully. |
| `failed` | Failed; `message` should explain why. |

Publishing to broker is not success. Only matching ACK closes the command loop.

## Heartbeat

Topic:

```text
wfm/{config_id}/{node_id}/heartbeat
```

Payload:

```json
{
  "client_online": true,
  "wg_online": true
}
```

Heartbeat is sent every 30 minutes and does not need ACK. The backend does not rely on heartbeat alone for online state.

## LWT and Retained

Retained should be false for `event`, `heartbeat`, and ACK messages.

LWT should publish an `offline` event to:

```text
wfm/{config_id}/{node_id}/event
```

An offline will message is an explicit offline signal. Later heartbeat, ACK, or non-offline event can mark the client reachable again.

## Online Projection

Console client states:

| State | Meaning |
| --- | --- |
| online | Recent reachable signal exists and no newer offline signal exists. |
| dropped | Reachable signals exceeded TTL, or detect failed/timed out. |
| offline | Will message received, never initialized, reset, changed to static, or permission revoked. |

Reachable signals:

- heartbeat
- detect ACK
- control ACK
- info ACK
- config push ACK
- non-offline event

Runtime state:

| State | Meaning |
| --- | --- |
| `unknown` | Static node, uninitialized dynamic node, offline/dropped client, or detect timeout. |
| `running` | Client reports current profile interface running. |
| `stopped` | Client reports current profile interface stopped. |

Raw `wg` / `awg` output is diagnostic only and does not affect runtime projection.

## Backend MQTT Client

The backend high-privilege MQTT client:

- Ensures the backend MQTT user exists in EMQX.
- Subscribes to all upstream topics.
- Parses heartbeat, event, and ACK messages.
- Writes runtime state to the database.
- Pushes SSE updates to the console.
- Sends periodic detect messages while there are active frontend subscribers.

## Client Privileges

Control commands are executed by the client service, not by backend privilege escalation.

| Platform | Service identity |
| --- | --- |
| Windows | `WfmAgent` Windows Service, `LocalSystem`. |
| Linux | `wfm-agent.service`, root. |
| macOS | `mesh.wg-free.wfm-agent` LaunchDaemon, root. |

If privileges are insufficient, the client should emit a clear event and return a failed ACK.
