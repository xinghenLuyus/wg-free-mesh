# Development Startup

This page describes the most common local development setup with three processes: EMQX started by Docker, the FastAPI backend started on the host machine, and the Vite frontend started on the host machine. For full Docker deployment, see [Docker Deploy](/en/deploy/).

## Version Requirements

Local development should stay aligned with the repository and Docker build environment:

| Component | Version / Constraint | Notes |
| --- | --- | --- |
| Python | `>=3.12` | Required by backend `src/pyproject.toml`. The recommended local setup is a conda environment such as `wfm`. |
| Node.js | `22.x` | Frontend Docker build uses `node:22-alpine`. |
| pnpm | `10.33.0` | Docker build pins this version. |
| EMQX | `5.8.5` | Docker Compose uses `emqx/emqx:5.8.5`. |

Dependency installation changes the local environment and should be done manually by the maintainer. Automation helpers must not install, upgrade, or remove dependencies on behalf of the maintainer.

## Startup Order

Start the development environment in this order:

1. Start EMQX with Docker.
2. Start the backend with `uvicorn`.
3. Start the frontend with `pnpm run dev`.

## 1. Start EMQX

Reuse the EMQX configuration from the SQLite deployment directory:

```bash
cd docker/sqlite
cp .env.example .env
```

Change the callback URL to the host machine:

```dotenv
WFM_EMQX_AUTHZ_URL=http://host.docker.internal:8000/api/internal/emqx/authz
```

Uncomment the EMQX Dashboard/API port `18083` in the compose file, otherwise EMQX callback and management features cannot work correctly during local development.

Start only EMQX:

```bash
docker compose up -d emqx
```

## 2. Start the Backend

The backend is started from `src/` and reads `src/.env`.

Enter the backend directory:

```bash
cd src
python -m pip install -e .[dev]
cp .env.example .env
```

Notes:

- `WFM_ENABLE_DEV_TEST_API=true` registers `/api/v0` and relaxes production source checks. Use it only for development.
- `WFM_EXTRA_ALLOWED_ORIGINS` must include the Vite frontend origin, otherwise browser requests from `5173` are rejected by source checks.
- `WFM_MQTT_URL` is the broker URL used by the backend. When the backend runs on the host and EMQX runs in Docker, use `127.0.0.1:1883`.
- `WFM_EMQX_API_BASE_URL` is the EMQX Dashboard/API URL used by the backend. This requires port `18083` to be exposed for development.
- `WFM_PUBLIC_ORIGIN` affects client downloads, bind commands, and some public URLs. For frontend local development, it usually points to the backend address.

Start with `uvicorn`:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-exclude data --timeout-graceful-shutdown 1
```

Common backend URLs:

- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/system/health`
- SSE: `http://127.0.0.1:8000/api/v1/events/stream`

## 3. Start the Frontend

The frontend uses Vite:

```bash
cd front
pnpm run dev
```

Open:

```text
http://127.0.0.1:5173
```

When the frontend runs on `5173`, API and SSE requests default to the same host on port `8000`:

```text
http://127.0.0.1:8000
```

If you need to explicitly set the backend URL before starting the frontend:

```bash
export VITE_API_BASE_URL='http://127.0.0.1:8000'
pnpm run dev
```

The frontend does not use Vite proxy. Cross-origin access during development is controlled by backend source settings.

## Common Issues

### The frontend opens, but API requests are rejected

Check `src/.env` first:

```dotenv
WFM_ENABLE_DEV_TEST_API=true
WFM_EXTRA_ALLOWED_ORIGINS=["http://127.0.0.1:5173","http://localhost:5173"]
```

If you access the frontend from a phone or another LAN device, add that origin to `WFM_EXTRA_ALLOWED_ORIGINS` and make sure the backend Host restriction allows that access path.

### The backend reports MQTT or EMQX errors

Check in order:

1. Whether the EMQX container is running.
2. Whether `1883` is mapped to the host.
3. Whether `18083` is temporarily exposed for development.
4. Whether `src/.env` and `docker/sqlite/.env` use the same EMQX username, password, and AuthZ shared key.
5. Whether `docker/sqlite/.env` points `WFM_EMQX_AUTHZ_URL` to `http://host.docker.internal:8000/api/internal/emqx/authz`.

### Backend reload keeps restarting

Confirm the startup command includes:

```bash
--reload-exclude data
```

`src/data` is the local runtime data directory. It stores the database, download artifacts, bulk config packages, and snapshots. Changes there should not trigger backend reloads.
