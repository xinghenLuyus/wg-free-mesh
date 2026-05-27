# Environment

Copy `.env.example` before deployment, then edit `.env`. Do not deploy with the example values unchanged.

```bash
cp .env.example .env
```

This page only lists variables that must be reviewed before startup. For the full list, see [Environment Reference](/en/reference/env).

## Required Changes

### Public Origin

```env
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

This is the main public origin of the system. The console, API, SSE, MCP, and client binding config all use it as the source of truth. Production deployments should use HTTPS.

For local testing, this can stay as:

```env
WFM_PUBLIC_ORIGIN=http://localhost:8000
```

### EMQX Password

```env
WFM_EMQX_USERNAME=admin
WFM_EMQX_PASSWORD=change-me
```

`WFM_EMQX_PASSWORD` is used for the EMQX Dashboard, management API, and backend MQTT superuser. Change it to a strong password in production.

### EMQX Authorization Secret

```env
WFM_EMQX_AUTHZ_SHARED_KEY=change-me-long-random-secret
```

EMQX uses this secret when calling the backend for topic authorization. Production deployments must use a long random value.

### EMQX Node Cookie

```env
WFM_EMQX_NODE_COOKIE=change-me-emqx-cookie
```

Change it even for single-node deployments. For EMQX clusters, all nodes must use the same cookie.

### PostgreSQL Password

PostgreSQL deployments must also change:

```env
WFM_POSTGRES_PASSWORD=change-me
WFM_DATABASE=postgresql+psycopg://wfm:change-me@postgres:5432/wfm
```

The password in `WFM_DATABASE` must match `WFM_POSTGRES_PASSWORD`.

## Development Switches

Keep these disabled in production:

```env
WFM_DEBUG=false
WFM_ENABLE_DEV_TEST_API=false
```

`WFM_ENABLE_DEV_TEST_API=true` bypasses production origin checks and exposes development test APIs. Use it only for local development.

## Extra Allowed Origins

If the production entrypoint is `https://wfm.example.com` but a local frontend needs temporary access to the backend, configure:

```env
WFM_EXTRA_ALLOWED_ORIGINS=["http://localhost:5173"]
```

This only extends Origin checks. It does not extend allowed Host values. The primary entrypoint is still controlled by `WFM_PUBLIC_ORIGIN`.

## MQTT Switch

Enable client binding, remote control, and node online status:

```env
WFM_ENABLE_MQTT_SERVICES=true
COMPOSE_PROFILES=mqtt
```

Disable MQTT completely:

```env
WFM_ENABLE_MQTT_SERVICES=false
COMPOSE_PROFILES=
```

When disabled, client binding, endpoint control, MQTT status, and related APIs are disabled at the system level.

## MQTT TLS

```env
WFM_MQTT_TLS_ENABLED=true
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
```

`WFM_MQTT_TLS_ENABLED=true` enables the client TLS listener and makes generated client binding configs prefer the TLS port. The backend still connects to EMQX over the internal Docker network by default.

## Next Steps

- Continue startup: [Docker Deploy](/en/deploy/).
- Public exposure: [Reverse Proxy](/en/deploy/reverse-proxy).
- Full variable list: [Environment Reference](/en/reference/env).
