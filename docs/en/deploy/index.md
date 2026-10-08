# Docker Deploy

Docker is currently the only recommended deployment path for WG Free Mesh.

This is not a single-process web application. It includes the console, backend API, database, EMQX, MQTT authorization, client TLS certificates, downloadable artifacts, snapshots, and a unified gateway. The Docker layout keeps these components in a predictable network and directory structure, and it automatically handles most EMQX details that are easy to misconfigure manually.

For production, read [Environment](/en/deploy/environment) before starting. If the service will be exposed publicly, also read [Reverse Proxy](/en/deploy/reverse-proxy) and publish the console and API through HTTPS.

## Clone the Repository

Clone the project and enter the repository directory first:

```bash
git clone https://github.com/xinghenLuyus/wg-free-mesh.git
cd wg-free-mesh
```

## Choose a Database

SQLite and PostgreSQL use the same application logic. Snapshots are exported at the application layer, so data can be migrated between the two modes.

| Mode | Best for | Notes |
| --- | --- | --- |
| SQLite | Local use, lightweight deployments, single-admin setups, small node counts | Data is stored directly in the project's `src/data` directory, making it easy to inspect, back up, and migrate. |
| PostgreSQL | Long-running services, multi-user use, higher concurrency, production | Starts an additional PostgreSQL database container and is better suited to long-running or production deployments. |

## Start with SQLite

Enter the SQLite deployment directory:

```bash
cd docker/sqlite
```

Copy the environment configuration file:

```bash
cp .env.example .env
```

Then edit `.env`.

At minimum, confirm the following:

- Change the passwords and keys required for production.

- Set `WFM_PUBLIC_ORIGIN` to the actual access URL.

For example:

```text
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

If you only need the web console and do not need client remote control or MQTT services, you can disable them:

```text
WFM_ENABLE_MQTT_SERVICES=false
COMPOSE_PROFILES=
```

See [Environment](/en/deploy/environment) for the full explanation.

After configuring `.env`, start the deployment:

```bash
docker compose up -d
```

Default URL:

```text
http://localhost:8000
```

## Start with PostgreSQL

Enter the PostgreSQL deployment directory and copy the environment configuration file:

```bash
cd docker/postgres
cp .env.example .env
```

Edit `.env`. At minimum, change:

- The PostgreSQL database password.

- The EMQX password.

- The shared secret.

- `WFM_PUBLIC_ORIGIN`.

For example:

```text
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

If you only need the web console and do not need client remote control or MQTT services, you can disable them:

```text
WFM_ENABLE_MQTT_SERVICES=false
COMPOSE_PROFILES=
```

See [Environment](/en/deploy/environment) for the full explanation.

After configuring `.env`, start the deployment:

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
