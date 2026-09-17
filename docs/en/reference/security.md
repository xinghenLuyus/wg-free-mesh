# Security Boundaries

## Source Restrictions

After `WFM_PUBLIC_ORIGIN` is configured in production, the system rejects requests whose Host is not the primary Host. When a browser sends an `Origin`, it must also belong to the allowed origin list.

Development test mode, `WFM_ENABLE_DEV_TEST_API=true`, skips source restrictions. Do not enable it in production.

## Administrator Password

The administrator password belongs only to the current deployment:

- It is not included in snapshots.
- It is not accepted through MCP.
- Restoring a snapshot does not overwrite it.

## MCP

MCP security boundaries are:

- Tokens have read or write permission.
- Write operations require confirmation.
- Calls are audited.
- Snapshot creation, import, restore, and deletion are not exposed.
- Snapshot passwords are not accepted.
- Download capabilities return short-lived URLs rather than file contents.

## Download Tokens

A download token authorizes one bound file or one bound endpoint config and expires after five minutes by default.

## MQTT

The backend is authoritative for MQTT users and authorization. It synchronizes state while EMQX is online and persists data first while EMQX is unavailable.

Resetting an endpoint client revokes its MQTT user and attempts to disconnect it.

## Snapshots

Snapshots are encrypted with the administrator password. All application-level data except the administrator password is included.
