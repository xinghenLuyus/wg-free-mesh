# Downloads

Download APIs support either an admin session or a short-lived scoped download token.

## File token kinds

| kind | resource |
| --- | --- |
| `client_artifact` | client artifact id |
| `config_bulk_package` | bulk package id |
| `snapshot_export` | snapshot id |

MCP download tools return URLs containing 5-minute scoped tokens. MCP does not transfer file bytes.
