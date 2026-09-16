# Application Update

Before updating, we recommend exporting a snapshot from System Settings. Snapshots contain application-level data and can be used to migrate between SQLite and PostgreSQL.

Enter the active deployment directory:

```bash
cd docker/sqlite
# or cd docker/postgres
```

Pull the latest containers and start the deployment again:

```bash
docker compose pull
docker compose up -d
```

Compose pulls the version selected by `WFM_IMAGE_TAG` in `.env`; when unset, it uses `latest`.
