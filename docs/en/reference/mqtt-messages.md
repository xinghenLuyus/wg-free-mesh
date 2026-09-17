# MQTT Messages

This page defines MQTT topics, message envelopes, message types, ACK rules, and online-state projection between the backend and `wfm-agent`.

MQTT is only the low-traffic control channel. The database remains the source of business truth, and EMQX is the transport executor.

## Enable and Disable

When `WFM_ENABLE_MQTT_SERVICES=false`:

- Client binding is unavailable.
- Endpoint control is unavailable.
- New dynamic endpoints are rejected; existing dynamic endpoints behave as static endpoints without changing stored data.
- MQTT write APIs return `MQTT_DISABLED`, and config synchronization stops at the server-side staged state.
- MQTT UI sections keep their layout but are disabled, while control and client-download pages cannot be opened.
- The backend must not depend on EMQX to start.

`COMPOSE_PROFILES` independently controls whether Docker deploys EMQX. When MQTT is enabled, the backend synchronizes accounts, authorization, and client state after EMQX is online.

## Connection Boundary

The backend connects through `WFM_MQTT_URL`, defaulting to Docker-internal plain MQTT:

```text
mqtt://emqx:1883
```

Client TLS is controlled by deployment and bind config. `WFM_MQTT_TLS_ENABLED=true` enables the client TLS listener and makes generated bind configs prefer TLS. It does not force backend-to-EMQX TLS.

If the deployer explicitly sets `WFM_MQTT_URL` to a `mqtts://` URL, the backend attempts TLS using that URL.

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

Tunnel protocol is not stored in the bind profile. Every command, config push, and detect payload carries `tunnel_protocol`; the client must use the current message to select the `wg` / `awg` toolchain.

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
- EMQX HTTP AuthZ must evaluate the exact node, topic, and action.

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

Fields:

| Field | Description |
| --- | --- |
| `type` | Message type, such as `heartbeat`, `event`, or `ack`. |
| `request_id` | Required for command-like messages; empty for passive messages. |
| `config_id` | Configuration containing the current node. |
| `node_id` | Current node. |
| `boot_id` | Unique identifier for this agent process start. |
| `session_id` | Unique MQTT session identifier for the current profile worker. |
| `sent_at` | UTC timestamp. |
| `payload` | Business payload. |

## Config Push

Purpose:

- Push the current node's staged config from the backend to the client.
- Confirm the transition from server synchronization state to client delivery state.
- Both console-triggered and automatic config delivery use this flow.

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
  "previous_tunnel_protocol": "amneziawg_2",
  "interface_name": "mesh-main-node-a",
  "config_version": 3,
  "config_sha256": "abc...",
  "config_text": "[Interface]\n..."
}
```

Supported `tunnel_protocol` values:

| Value | Client behavior |
| --- | --- |
| `wireguard` | Use `wg` for status, `wg-quick` on Linux/macOS, and `wireguard.exe` tunnel-service commands on Windows. |
| `amneziawg_2` | Use `awg` for status, `awg-quick` on Linux/macOS, and `amneziawg.exe` tunnel-service commands on Windows. |

`previous_tunnel_protocol` identifies the original toolchain that the client must inspect and clean before replacing the config. It is the same as `tunnel_protocol` when the protocol has not changed.

The client inspects both `previous_tunnel_protocol` and the target protocol for the current profile. Before overwriting the config, it stops every running matching interface with its corresponding toolchain and returns `failed` if any stop fails. After all interfaces stop, it writes the new config. If an interface was running before the update, it restarts with the target toolchain; otherwise it only writes the config. Only the complete sequence returns `applied`.

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

Downstream topic:

```text
wfm/{config_id}/{node_id}/detect
```

ACK topic:

```text
wfm/{config_id}/{node_id}/detect/ack
```

Rules:

- Probe only while the frontend has active SSE subscriptions.
- The recommended interval is once every 2 minutes.
- Do not probe when nobody is viewing the console.
- The `detect` payload carries `tunnel_protocol`; the client uses it to inspect the current profile interface.
- If no ACK arrives before the timeout, the backend may mark the probe as failed.

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

`client_version` must come from the single version injected at client build time. The backend uses it to refresh the client-version field in the control panel.

`wg_online` only describes the interface named by the current profile's `interface_name`; it does not mean that any WireGuard or AmneziaWG interface exists on the host.

## Info

`info` requests diagnostics in response to a user action.

Downstream topic:

```text
wfm/{config_id}/{node_id}/info
```

ACK topic:

```text
wfm/{config_id}/{node_id}/info/ack
```

It currently runs raw `wg` or `awg` and returns command output through `event`. `info/ack` only marks success or failure; stdout, stderr, and diagnostic text are always sent through `event`.

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

Rules:

- `event` does not need an ACK.
- The backend stores, displays, and cleans up events.
- Command output may only appear in `event`, never in an ACK.
- A non-`offline` event can count as a recent reachable signal.

## ACK

ACK is required for:

- `config/push`
- `control`
- `detect`
- `info`

ACK is not required for:

- `event`
- `heartbeat`

Common ACK payload:

```json
{
  "status": "applied",
  "message": "Command completed",
  "action": "start"
}
```

Allowed `status` values:

| status | Meaning |
| --- | --- |
| `accepted` | Received or queued. |
| `applied` | Completed successfully. |
| `failed` | Failed; `message` should explain why. |

Rules:

- Successfully publishing to the broker does not mean the command succeeded.
- Only an ACK with the same `request_id` closes the command loop.
- Every ACK also proves that the client is currently reachable and refreshes `last_reachable_at`.
- ACK messages do not carry command output.

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

Rules:

- Heartbeat does not need an ACK.
- The client sends one every 30 minutes.
- The backend does not rely on heartbeat alone for online state.
- `wg_online` only describes the current profile interface.

## LWT and Retained

Retained should be false for `event`, `heartbeat`, and ACK messages.

LWT should publish an `offline` event to:

```text
wfm/{config_id}/{node_id}/event
```

Payload:

```json
{
  "type": "event",
  "config_id": "cfg_xxx",
  "node_id": "node_xxx",
  "boot_id": "",
  "session_id": "",
  "sent_at": "2026-04-23T12:10:00Z",
  "payload": {
    "level": "info",
    "event": "offline",
    "message": "Client disconnected with will message."
  }
}
```

Rules:

- A will message is an explicit offline signal.
- After receiving it, the console state converges to `offline`.
- A later heartbeat, ACK, or non-`offline` event proves that the client is reachable again and restores `online` or resumes runtime-state projection.

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

The 30-minute heartbeat interval reduces traffic. The online TTL must be longer than the heartbeat interval so one lost heartbeat does not cause a false disconnect.

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

The first phase does not place business truth in the EMQX rule engine.

## Client Privileges

Control commands are executed by the client service, not by backend privilege escalation.

| Platform | Service identity |
| --- | --- |
| Windows | `WfmAgent` Windows Service, `LocalSystem`. |
| Linux | `wfm-agent.service`, root. |
| macOS | `mesh.wg-free.wfm-agent` LaunchDaemon, root. |

If the client is not running as a system service or lacks privileges, it must emit a clear error through `event` and return `failed` through the corresponding ACK.

## EMQX Authorization

EMQX calls the backend through the internal endpoint:

```http
POST /api/internal/emqx/authz
x-wfm-internal-key: <WFM_EMQX_AUTHZ_SHARED_KEY>
```

Allow response:

```json
{ "result": "allow" }
```

Deny response:

```json
{ "result": "deny" }
```

When an endpoint client is reset, the backend clears its client state, deletes or disables its EMQX user, and attempts to disconnect the corresponding MQTT client.
