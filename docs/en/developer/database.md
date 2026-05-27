# Database

Database access is unified through SQLAlchemy. SQLite and PostgreSQL are currently supported.

The database is the business source of truth. Read the source-of-truth section in [Architecture](./architecture), then use this page for migrations and repositories.

## Entry Points

| File or directory | Purpose |
| --- | --- |
| `src/app/data/schema.py` | SQLAlchemy table definitions. |
| `src/app/data/database.py` | Engine, connections, and initialization. |
| `src/app/data/repositories` | Business repository mixins. |
| `src/migrations` | Alembic migrations. |
| `src/alembic.ini` | Alembic config. |

## Migrations

Schema changes must go through Alembic migrations. Changing only `schema.py` will not update existing databases.

Startup initializes and migrates the database so SQLite and PostgreSQL can move to the current schema.

Migration scripts should:

- Work on SQLite and PostgreSQL.
- Avoid database-specific SQL unless dialect branches are used.
- Handle existing data, nulls, and defaults.
- Consider snapshot restore semantics.

Field meanings and relationships must be reflected in [Data Model](/en/reference/data-model). Restore behavior must be reflected in [Snapshots](/en/reference/snapshot).

## Repositories

Repositories own SQL reads, writes, and transaction boundaries. Services should not assemble SQL or depend on database-specific behavior.

To add another database, keep repository interfaces stable and extend connection plus migration compatibility.

## Snapshots

Snapshots are application-level backups, not database file backups. They should include application business data except the administrator password and work across SQLite and PostgreSQL.

After restore, the database remains the source of truth. External systems such as EMQX are synchronized from the restored database state.

If snapshots include client MQTT credentials, also check [MQTT Protocol](./mqtt-protocol) and [Client Lifecycle](/en/reference/client-lifecycle).

## Connection Pooling

SQLAlchemy manages connection pooling. PostgreSQL benefits from pooling; SQLite is intended for lightweight deployments.

During startup, the database may not be ready yet, especially on first PostgreSQL container startup. The app retries before failing.

## Related Docs

- [Backend](./backend)
- [Data Model](/en/reference/data-model)
- [Snapshots](/en/reference/snapshot)
- [Environment Reference](/en/reference/env)
- [Docker Deploy](/en/deploy/)
