# Snapshot Reference

A snapshot is an application-level backup, not a database-file backup. It supports migration of application data between databases such as SQLite and PostgreSQL.

## Included Data

All application data in the database except the administrator password is included, such as:

- Configs.
- Endpoints.
- Mesh pairs.
- Synchronization state.
- Runtime records.
- Client binding state and MQTT credentials.
- MCP tokens and audit data.
- Settings.

## Excluded Data

The administrator password is not included. Restoring a snapshot does not overwrite the current deployment's administrator password.

## Encryption

Snapshots are encrypted with the administrator password and cannot be read without it.

## Export

Snapshots can be exported from the system page. MCP can also use `write_export_snapshot` to create a five-minute download URL.

MCP does not transfer snapshot file contents.

## Restore

Restore is available only from the system page. MCP does not expose restore and does not accept snapshot passwords.

Restore clears old business data and imports the snapshot data. The backend then rebuilds runtime projections and synchronizes MQTT users and authorization when EMQX is online.

## Compatibility

A snapshot records the current system version so its origin can be identified. The current implementation does not block cross-version restore.
