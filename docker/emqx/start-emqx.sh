#!/bin/sh
set -eu

CONFIG_DIR="/opt/emqx/etc"
TLS_CONFIG="/opt/emqx/wfm/base.tls.hocon"
PLAIN_CONFIG="/opt/emqx/wfm/base.hocon"
TARGET_CONFIG="${CONFIG_DIR}/base.hocon"
API_KEY_FILE="${CONFIG_DIR}/wfm-api-keys.conf"
AUTHZ_URL="${WFM_EMQX_AUTHZ_URL:-http://host.docker.internal:8000/api/internal/emqx/authz}"
AUTHZ_KEY="${WFM_EMQX_AUTHZ_SHARED_KEY:-wfm-internal-emqx-authz}"
EMQX_USERNAME="${WFM_EMQX_USERNAME:-admin}"
EMQX_PASSWORD="${WFM_EMQX_PASSWORD:-public}"

if [ "${WFM_MQTT_TLS_ENABLED:-false}" = "true" ]; then
  if [ ! -f "/opt/emqx/etc/certs/server.crt" ] || [ ! -f "/opt/emqx/etc/certs/server.key" ]; then
    echo "WFM_MQTT_TLS_ENABLED=true but EMQX cert files are missing under /opt/emqx/etc/certs" >&2
    exit 1
  fi
  cp "${TLS_CONFIG}" "${TARGET_CONFIG}"
else
  cp "${PLAIN_CONFIG}" "${TARGET_CONFIG}"
fi

sed -i "s|__WFM_EMQX_AUTHZ_URL__|${AUTHZ_URL}|g" "${TARGET_CONFIG}"
sed -i "s|__WFM_EMQX_AUTHZ_SHARED_KEY__|${AUTHZ_KEY}|g" "${TARGET_CONFIG}"

printf "%s:%s:administrator\n" "${EMQX_USERNAME}" "${EMQX_PASSWORD}" > "${API_KEY_FILE}"

exec /opt/emqx/bin/emqx foreground
