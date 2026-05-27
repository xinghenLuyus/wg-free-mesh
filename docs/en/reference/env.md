# Environment Reference

Environment variables use the `WFM_` prefix. Docker examples live in `docker/sqlite/.env.example` and `docker/postgres/.env.example`.

## Runtime

| Variable | Meaning |
| --- | --- |
| `WFM_DEBUG` | Backend debug mode. |
| `WFM_ENABLE_DEV_TEST_API` | Enables `/api/v0` and skips production source guard. |
| `WFM_TIMEZONE` | Display timezone. |
| `WFM_AUTH_TOKEN_EXPIRE_MINUTES` | Admin token lifetime. |
| `WFM_AUTH_DOWNLOAD_TOKEN_EXPIRE_MINUTES` | Download token lifetime. |

## Public access

| Variable | Meaning |
| --- | --- |
| `WFM_PUBLIC_ORIGIN` | Main public origin. |
| `WFM_EXTRA_ALLOWED_ORIGINS` | Extra allowed browser origins as JSON array. |
| `WFM_APP_PORT` | Host Gateway Web port. |
| `WFM_GATEWAY_CLIENT_MAX_BODY_SIZE` | Gateway request body limit. |

## Database

| Variable | Meaning |
| --- | --- |
| `WFM_DATABASE` | SQLAlchemy database URL. |
| `WFM_POSTGRES_DB` | PostgreSQL database name. |
| `WFM_POSTGRES_USER` | PostgreSQL user. |
| `WFM_POSTGRES_PASSWORD` | PostgreSQL password. |
| `WFM_POSTGRES_PORT` | Host PostgreSQL port. |

## MQTT / EMQX

| Variable | Meaning |
| --- | --- |
| `WFM_ENABLE_MQTT_SERVICES` | Enables client binding, MQTT, and endpoint control. |
| `COMPOSE_PROFILES` | Compose profile, usually `mqtt`. |
| `WFM_MQTT_URL` | Backend MQTT broker URL. |
| `WFM_MQTT_PUBLIC_PORT` | Client plaintext MQTT port. |
| `WFM_MQTT_PUBLIC_TLS_PORT` | Client TLS MQTT port. |
| `WFM_MQTT_TLS_ENABLED` | Enables client-facing MQTT TLS. |
| `WFM_EMQX_API_BASE_URL` | Internal EMQX management API URL. |
| `WFM_EMQX_USERNAME` | EMQX admin username. |
| `WFM_EMQX_PASSWORD` | EMQX admin password. |
| `WFM_EMQX_AUTHZ_SHARED_KEY` | Internal EMQX authz shared key. |
| `WFM_EMQX_AUTHZ_URL` | Backend authz callback URL. |
