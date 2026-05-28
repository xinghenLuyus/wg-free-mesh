# Docker Deploy

Docker is currently the only recommended deployment path for WG Free Mesh.

This is not a single-process web application. It includes the console, backend API, database, EMQX, MQTT authorization, client TLS certificates, downloadable artifacts, snapshots, and a unified gateway. The Docker layout keeps these components in a predictable network and directory structure, and it automatically handles most EMQX details that are easy to misconfigure manually.

For production, read [Environment](/en/deploy/environment) before starting. If the service will be exposed publicly, also read [Reverse Proxy](/en/deploy/reverse-proxy) and publish the console and API through HTTPS.

## Choose a Database

SQLite and PostgreSQL use the same application logic. Snapshots are exported at the application layer, so data can be migrated between the two modes.

| Mode | Best for | Notes |
| --- | --- | --- |
| SQLite | Local use, lightweight deployments, single-admin setups, small node counts | File-based database, simple deployment, straightforward backup, low resource usage. |
| PostgreSQL | Long-running services, multi-user use, higher concurrency, production | Dedicated database service, more stable concurrency and connection pooling, better for future growth. |

Choose SQLite if you only want to get started. Choose PostgreSQL for long-term production use.

## Before Starting

Check these items first:

- `.env.example` has been copied to `.env`.
- Production passwords and shared secrets have been changed.
- `WFM_PUBLIC_ORIGIN` is set to the real access URL, for example `https://wfm.example.com`.
- If MQTT, client control, and remote status are not needed, `WFM_ENABLE_MQTT_SERVICES` is disabled and `COMPOSE_PROFILES` is empty.
- If the service is public, HTTPS reverse proxying is ready.

See [Environment](/en/deploy/environment) for details.

## Start with SQLite

SQLite is the smallest deployment mode. Data is mounted into the project `src/data` directory for local inspection, backup, and migration.

```bash
cd docker/sqlite
cp .env.example .env
```

Edit `.env`, then start:

```bash
docker compose up -d
```

Default URL:

```text
http://localhost:8000
```

## Start with PostgreSQL

The PostgreSQL layout starts an additional database container. This is the recommended production mode.

```bash
cd docker/postgres
cp .env.example .env
```

Edit `.env`. At minimum, change the PostgreSQL password, EMQX password, and shared secret. Then start:

```bash
docker compose up -d
```

Default URL:

```text
http://localhost:8000
```

## After Startup

Open the console and complete administrator initialization. Then create a config, add nodes, download the client, and bind nodes.

If MQTT is enabled, EMQX may become ready later than the backend. Seeing temporary EMQX or node waiting states is normal. Once EMQX is online, the backend synchronizes accounts, authorization, and client connection data.

## Image Version

Docker deployment uses the `latest` image by default. `latest` points to the current public recommended version. Before the first stable release, it points to the newest RC release.

Most deployments do not need to manage image tags. Start normally:

```bash
docker compose up -d
```

If you need a fixed production version and do not want to follow `latest`, set the image tag in `.env`:

```env
WFM_IMAGE_TAG=1.0.0
```

Pre-release versions can also be pinned:

```env
WFM_IMAGE_TAG=1.0.0-rc.1
```

## Update

Export a snapshot from system settings before updating. Snapshots are application-level data and can be used to migrate between SQLite and PostgreSQL.

From the selected Docker directory, start the services again:

```bash
docker compose up -d
```
