# Backups

Snapshots are application-level backups for WG Free Mesh. They do not depend on a specific database file, so they can migrate data between SQLite and PostgreSQL.

## What Snapshots Include

Except for the administrator password, business data in the application database should be included:

- System settings.
- Configs.
- Nodes.
- Mesh pairs.
- Client state and MQTT credentials.
- MCP Tokens.
- Audit records.
- Port forwarding rules.
- Advanced protocol parameters.

Snapshots include the current system version for source-version awareness, but no strict compatibility check is currently enforced.

## What Snapshots Exclude

Snapshots do not include the administrator password. After restore, administrator identity is still controlled by the current system initialization and login flow.

Deployment-level environment variables are also not restored from snapshots, including database connection, public origin, Docker ports, and whether MQTT is enabled. These belong in `.env`.

## Security

Snapshots are encrypted with the administrator password. Without the password, the snapshot content should not be directly readable.

Treat exported snapshots like database backups. Do not upload them to public repositories or chat windows.

## Restore Flow

Restoring a snapshot can take some time. The frontend shows a blocking restore dialog to prevent other operations while data is being replaced.

Restore replaces current application data with snapshot content. Export the current state first if a rollback path is needed.

## EMQX Synchronization

The backend database is the source of truth. After snapshot restore, if EMQX is online, the backend synchronizes node accounts, authorization, and client connection data to EMQX. If EMQX is offline, data is stored first and synchronized after EMQX becomes available.

## Database Migration

Recommended SQLite to PostgreSQL migration:

1. Export a snapshot from the SQLite deployment.
2. Start the PostgreSQL deployment.
3. Initialize the administrator.
4. Import and restore the snapshot.
5. Check configs, nodes, and client state.

The reverse migration uses the same process.
