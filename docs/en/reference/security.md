# Security

Production deployments restrict Host and browser Origin according to `WFM_PUBLIC_ORIGIN` and extra allowed origins.

The administrator password is deployment-local and is not included in snapshots.

MCP boundaries:

- read/write token separation
- confirmation for write tools
- audit logging
- no snapshot create/import/restore/delete
- no snapshot password input
- download tools return short-lived URLs only

MQTT users and authorization are reconciled from database state.
