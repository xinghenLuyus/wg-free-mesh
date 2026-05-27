# Client

The client lives in `client/` and is implemented in Go. It has two entrypoints:

- `wfm-agent`: long-running system service.
- `wfmctl`: CLI for install, bind, status, logs, and service control.

This page explains implementation boundaries. User-facing download, install, and CLI usage live in [Client and Control](/en/usage/client).

## Main Directories

| Directory | Purpose |
| --- | --- |
| `client/cmd/agent` | Agent entrypoint. |
| `client/cmd/ctl` | wfmctl entrypoint. |
| `client/internal` | Binding, service management, MQTT, WireGuard/AmneziaWG operations. |
| `client/build_release.py` | Release build script. |

## Runtime Model

`wfmctl install` installs the system service and adds the client directory to PATH. The running `wfm-agent` reads local profiles, connects to MQTT, and waits for backend config and control commands.

Local state includes:

- profile: node identity, server URL, and MQTT parameters.
- desired config: what the backend wants the client to apply.
- applied config: what the client has applied.
- runtime/logs: service runtime information and logs.

## Binding

1. The console creates a one-time bind command.
2. The user runs `wfmctl bind --server <url> --token <token>`.
3. The client calls the backend bind API.
4. The backend validates the token and generates or rotates MQTT credentials.
5. The client writes the local profile.
6. If the service is running, the client attempts to restart it.

Bind tokens are single-use and expire.

For complete page flow, bind command generation, and control page switching, see [Client Lifecycle](/en/reference/client-lifecycle).

## MQTT Behavior

The client receives config pushes, control commands, and detect requests.

It reports heartbeat, info, events, detect ACKs, control ACKs, and config push ACKs.

MQTT disconnect and reconnect success are logged. High-frequency checks and retry attempts are not logged continuously.

For full topics, payloads, ACKs, LWT, and online projection, see [MQTT Messages](/en/reference/mqtt-messages). Backend boundaries are in [MQTT Protocol](./mqtt-protocol).

## WireGuard / AmneziaWG

The client calls local toolchains:

- WireGuard: `wg`, `wireguard.exe`, `wg-quick`.
- AmneziaWG: `awg`, `amneziawg.exe`, `awg-quick`.

Windows tunnel control uses GUI toolchain capabilities. Linux and macOS rely more on `wg-quick` / `awg-quick`, which is also where lifecycle hooks are effective.

WireGuard and AmneziaWG parameter rules are in [Protocols](/en/reference/protocols). Port forwarding depends on lifecycle hooks; see [Port Forwarding](/en/usage/port-forward).

## Logging

Log key state changes: service start/stop, profile loading, MQTT connection changes, config push result, control command result, and toolchain errors.

Avoid logging high-frequency retry loops.

## Related Docs

- [Client Lifecycle](/en/reference/client-lifecycle)
- [MQTT Messages](/en/reference/mqtt-messages)
- [Protocols](/en/reference/protocols)
- [API Contract](./api-contract)
- [Client and Control](/en/usage/client)
