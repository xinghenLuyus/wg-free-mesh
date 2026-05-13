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
CERT_DIR="/opt/emqx/etc/certs"
CA_CERT="${CERT_DIR}/ca.crt"
CA_KEY="${CERT_DIR}/ca.key"
SERVER_CERT="${CERT_DIR}/server.crt"
SERVER_KEY="${CERT_DIR}/server.key"
SERVER_CSR="${CERT_DIR}/server.csr"
SERVER_EXT="${CERT_DIR}/server.ext"
MQTT_PUBLIC_HOST="${WFM_MQTT_PUBLIC_HOST:-localhost}"
MQTT_CERT_HOST="${MQTT_PUBLIC_HOST#[}"
MQTT_CERT_HOST="${MQTT_CERT_HOST%]}"

is_ip_address() {
  case "$1" in
    *[!0-9.]* | "" | *.*.*.*.*) return 1 ;;
    *.*.*.*) return 0 ;;
    *) return 1 ;;
  esac
}

write_server_ext() {
  san="DNS:localhost,IP:127.0.0.1"
  if [ "${MQTT_CERT_HOST}" != "localhost" ] && [ "${MQTT_CERT_HOST}" != "127.0.0.1" ]; then
    if is_ip_address "${MQTT_CERT_HOST}"; then
      san="${san},IP:${MQTT_CERT_HOST}"
    elif [ "${MQTT_CERT_HOST#*:}" != "${MQTT_CERT_HOST}" ]; then
      san="${san},IP:${MQTT_CERT_HOST}"
    else
      san="${san},DNS:${MQTT_CERT_HOST}"
    fi
  fi
  {
    echo "basicConstraints = CA:FALSE"
    echo "keyUsage = digitalSignature, keyEncipherment"
    echo "extendedKeyUsage = serverAuth"
    echo "subjectAltName = ${san}"
  } > "${SERVER_EXT}"
}

ensure_tls_certs() {
  if [ -f "${CA_CERT}" ] && [ -f "${SERVER_CERT}" ] && [ -f "${SERVER_KEY}" ]; then
    return
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    echo "WFM_MQTT_TLS_ENABLED=true but openssl is not available to generate EMQX TLS certs" >&2
    exit 1
  fi
  umask 077
  mkdir -p "${CERT_DIR}"
  rm -f "${CA_CERT}" "${CA_KEY}" "${SERVER_CERT}" "${SERVER_KEY}" "${SERVER_CSR}" "${SERVER_EXT}" "${CERT_DIR}/ca.srl"
  openssl genrsa -out "${CA_KEY}" 4096
  openssl req -x509 -new -nodes -key "${CA_KEY}" -sha256 -days 3650 -out "${CA_CERT}" -subj "/CN=WG Free Mesh Local CA"
  openssl genrsa -out "${SERVER_KEY}" 2048
  openssl req -new -key "${SERVER_KEY}" -out "${SERVER_CSR}" -subj "/CN=${MQTT_CERT_HOST}"
  write_server_ext
  openssl x509 -req -in "${SERVER_CSR}" -CA "${CA_CERT}" -CAkey "${CA_KEY}" -CAcreateserial -out "${SERVER_CERT}" -days 3650 -sha256 -extfile "${SERVER_EXT}"
  rm -f "${SERVER_CSR}" "${SERVER_EXT}" "${CERT_DIR}/ca.srl"
}

if [ "${WFM_MQTT_TLS_ENABLED:-false}" = "true" ]; then
  ensure_tls_certs
  cp "${TLS_CONFIG}" "${TARGET_CONFIG}"
else
  cp "${PLAIN_CONFIG}" "${TARGET_CONFIG}"
fi

sed -i "s|__WFM_EMQX_AUTHZ_URL__|${AUTHZ_URL}|g" "${TARGET_CONFIG}"
sed -i "s|__WFM_EMQX_AUTHZ_SHARED_KEY__|${AUTHZ_KEY}|g" "${TARGET_CONFIG}"

printf "%s:%s:administrator\n" "${EMQX_USERNAME}" "${EMQX_PASSWORD}" > "${API_KEY_FILE}"

exec /opt/emqx/bin/emqx foreground
