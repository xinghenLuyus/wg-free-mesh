# Environment Reference

Environment variables use the `WFM_` prefix. Docker examples live in `docker/sqlite/.env.example` and `docker/postgres/.env.example`.

## Runtime

| Variable | Default | Meaning |
| --- | --- | --- |
| `WFM_DEBUG` | `false` | Backend debug mode. |
| `WFM_ENABLE_DEV_TEST_API` | `false` | Development exception switch; enables `/api/v0` and skips production source restrictions. |
| `WFM_TIMEZONE` | `Asia/Shanghai` | Console display timezone. |
| `WFM_AUTH_TOKEN_EXPIRE_MINUTES` | `1440` | Administrator login token lifetime. |
| `WFM_AUTH_DOWNLOAD_TOKEN_EXPIRE_MINUTES` | `5` | Download token lifetime. |

## Public access / Gateway

| Variable | Default | Meaning |
| --- | --- | --- |
| `WFM_PUBLIC_ORIGIN` | `http://localhost:8000` | Primary service origin. Use the public HTTPS entry in production. |
| `WFM_EXTRA_ALLOWED_ORIGINS` | `[]` | Additional allowed origins as a JSON array. Extends Origin only, not Host. |
| `WFM_APP_PORT` | `8000` | Gateway Web port exposed on the host. |
| `WFM_GATEWAY_CLIENT_MAX_BODY_SIZE` | `512m` | Gateway request-body limit, including snapshot imports. |

## Database

| Variable | Example | Meaning |
| --- | --- | --- |
| `WFM_DATABASE` | `sqlite:///./data/wg_free_mesh.db` | SQLAlchemy database URL. |
| `WFM_POSTGRES_DB` | `wfm` | PostgreSQL container initialization database. |
| `WFM_POSTGRES_USER` | `wfm` | PostgreSQL user. |
| `WFM_POSTGRES_PASSWORD` | `wfm` | PostgreSQL password. |
| `WFM_POSTGRES_PORT` | `5432` | PostgreSQL port exposed on the host. |

## MQTT / EMQX

| Variable | Default | Meaning |
| --- | --- | --- |
| `WFM_ENABLE_MQTT_SERVICES` | `true` | Enables dynamic endpoints, client binding, MQTT, and remote control. Existing dynamic endpoints behave as static when disabled. |
| `COMPOSE_PROFILES` | `mqtt` | Independently controls whether Docker Compose starts the EMQX profile. |
| `WFM_MQTT_URL` | `mqtt://emqx:1883` | Internal broker URL used by the backend. |
| `WFM_MQTT_PUBLIC_PORT` | `1883` | Client plaintext MQTT port. |
| `WFM_MQTT_PUBLIC_TLS_PORT` | `8883` | Client TLS MQTT port. |
| `WFM_MQTT_TLS_ENABLED` | `true` | Enables the client-facing MQTT TLS listener. |
| `WFM_EMQX_API_BASE_URL` | `http://emqx:18083` | Internal EMQX management API URL used by the backend. |
| `WFM_EMQX_USERNAME` | `admin` | EMQX Dashboard, management API, and backend MQTT superuser name. |
| `WFM_EMQX_PASSWORD` | `public` | EMQX password; must be changed in production. |
| `WFM_EMQX_NODE_COOKIE` | `wfm-emqx-cookie` | EMQX node cookie. |
| `WFM_EMQX_AUTHZ_SHARED_KEY` | `wfm-internal-emqx-authz` | Shared key for EMQX HTTP AuthZ callbacks; must be changed in production. |
| `WFM_EMQX_AUTHZ_URL` | `http://app:8000/api/internal/emqx/authz` | Internal backend callback used for topic authorization. |
