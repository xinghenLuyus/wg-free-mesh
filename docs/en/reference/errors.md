# Error Codes

Error responses always include:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Readable message",
    "detail": {}
  }
}
```

## General

| Code | Description |
| --- | --- |
| `VALIDATION_ERROR` | Request validation failed. |
| `PUBLIC_HOST_REJECTED` | The request Host is not the configured production Host. |
| `PUBLIC_ORIGIN_REJECTED` | The browser Origin is not allowed. |

## Authentication

| Code | Description |
| --- | --- |
| `AUTH_SETUP_REQUIRED` | The administrator password has not been initialized. |
| `AUTH_ALREADY_INITIALIZED` | The administrator password is already initialized. |
| `AUTH_REQUIRED` | Administrator authentication is missing. |
| `AUTH_FAILED` | The username, password, or current password is incorrect. |
| `ADMIN_PASSWORD_INVALID` | Administrator password verification failed for a business operation. |
| `INVALID_TOKEN` | The token is invalid. |
| `TOKEN_EXPIRED` | The token has expired. |
| `PASSWORD_UNCHANGED` | The new password must differ from the current password. |

## Downloads

| Code | Description |
| --- | --- |
| `DOWNLOAD_TOKEN_REQUIRED` | A download token is required. |
| `INVALID_DOWNLOAD_TOKEN` | The download token is invalid. |
| `INVALID_DOWNLOAD_RESOURCE` | The download resource kind is invalid. |
| `DOWNLOAD_TOKEN_SCOPE_MISMATCH` | The token does not match the requested file. |
| `CLIENT_ARTIFACT_NOT_FOUND` | The client artifact does not exist. |
| `GITHUB_RELEASE_ASSET_NOT_FOUND` | No matching client package exists in the current version's GitHub Release. |
| `GITHUB_RELEASE_DOWNLOAD_FAILED` | The GitHub Release client-package check failed. |
| `CONFIG_BULK_PACKAGE_NOT_FOUND` | The bulk config package does not exist. |
| `CONFIG_BULK_EMPTY_SELECTION` | No downloadable endpoint was selected. |
| `CONFIG_BULK_NODE_NOT_READY` | An endpoint has no downloadable staged config. |

## Configs and Endpoints

| Code | Description |
| --- | --- |
| `CONFIG_NOT_FOUND` | The config does not exist. |
| `CONFIG_NAME_EXISTS` | The config name already exists. |
| `INVALID_CONFIG_NAME` | The config name is invalid. |
| `INVALID_SUBNET` | The virtual subnet is invalid. |
| `NODE_NOT_FOUND` | The endpoint does not exist. |
| `NODE_CONFIG_MISMATCH` | The endpoint does not belong to the specified config. |
| `NODE_DISABLED` | The operation is unavailable for a disabled endpoint. |
| `INVALID_NODE_NAME` | The endpoint name is invalid. |
| `INVALID_VIRTUAL_IP` | The virtual IP is invalid. |
| `IP_POOL_EXHAUSTED` | The virtual subnet has no available address. |
| `INVALID_TAG` | The tag is invalid. |

## Mesh and Sync

| Code | Description |
| --- | --- |
| `INVALID_PEER_LINK` | The Mesh pair is invalid. |
| `PEER_LINK_NOT_FOUND` | The Mesh pair does not exist. |
| `INVALID_ALLOWED_IPS` | AllowedIPs is invalid. |
| `INVALID_ENDPOINT` | A manual Endpoint is missing its Host or Port. |
| `TOPOLOGY_INVALID` | Topology validation failed, so synchronization is blocked. |
| `NO_STAGED_CONFIG` | No staged config is available to push. |
| `CONTROL_LOG_NOT_FOUND` | The control log does not exist. |

## Quick Mesh

| Code | Description |
| --- | --- |
| `INVALID_QUICK_MESH_MODE` | The Quick Mesh mode is invalid. |
| `INVALID_ENDPOINT_FAMILY` | The Endpoint address family is invalid. |
| `QUICK_MESH_NOT_ENOUGH_NODES` | Fewer than two endpoints are enabled. |
| `QUICK_MESH_HUB_REQUIRED` | The gateway endpoint is missing or unavailable. |
| `QUICK_MESH_GATEWAY_REQUIRED` | Free Mesh requires at least one available gateway. |
| `QUICK_MESH_LEAF_INVALID` | A leaf endpoint is invalid. |
| `QUICK_MESH_NODE_ROLE_CONFLICT` | An endpoint cannot be both a gateway and a leaf. |
| `QUICK_MESH_LEAF_GATEWAY_INVALID` | A leaf references a gateway that was not selected. |
| `QUICK_MESH_NODE_UNASSIGNED` | An enabled endpoint has no assigned role. |

## AmneziaWG

| Code | Description |
| --- | --- |
| `INVALID_TUNNEL_PROTOCOL` | The tunnel protocol is invalid. |
| `INVALID_AWG_PARAMETER` | An AWG parameter is outside its valid range. |
| `INVALID_AWG_H_RANGE` | An H parameter has an invalid format, range, or overlap. |
| `INVALID_AWG_J_RANGE` | Jmax must be greater than Jmin. |

## MQTT and Client

| Code | Description |
| --- | --- |
| `MQTT_DISABLED` | MQTT services are disabled by deployment configuration. |
| `MQTT_TLS_CA_NOT_READY` | The client TLS CA certificate is not ready. |
| `MQTT_CONTROL_UNAVAILABLE` | The MQTT control channel is unavailable. |
| `INVALID_ACTION` | The control action is invalid. |
| `CLIENT_BIND_STATIC_NODE` | A static endpoint cannot bind a client. |
| `CLIENT_BIND_TOKEN_INVALID` | The bind token is invalid. |
| `CLIENT_BIND_TOKEN_USED` | The bind token has already been used. |
| `CLIENT_BIND_TOKEN_EXPIRED` | The bind token has expired. |
| `CLIENT_BIND_NOT_ALLOWED` | Client binding is not allowed for this endpoint. |

## Port Forwarding

| Code | Description |
| --- | --- |
| `PORT_FORWARD_SAME_NODE` | The From and To endpoints must differ. |
| `PORT_FORWARD_TO_PLATFORM_INVALID` | The destination platform must be Linux or macOS. |
| `PORT_FORWARD_PROTOCOL_INVALID` | The protocol must be TCP, UDP, or all. |
| `PORT_FORWARD_TO_PORT_IN_USE` | The To port is managed by another rule. |
| `PORT_FORWARD_NOT_FOUND` | The port-forward rule does not exist. |
| `PORT_FORWARD_NODE_INVALID` | An endpoint is outside the config or disabled. |
| `PORT_FORWARD_VIRTUAL_IP_REQUIRED` | An endpoint is missing its virtual IP. |
| `PORT_FORWARD_PORT_INVALID` | The port is invalid. |
| `PORT_FORWARD_IPV4_REQUIRED` | Port forwarding currently requires an IPv4 virtual IP. |

## Snapshots

| Code | Description |
| --- | --- |
| `SNAPSHOT_NOT_FOUND` | The snapshot does not exist. |
| `SNAPSHOT_INVALID_ARCHIVE` | The snapshot archive is invalid. |
| `SNAPSHOT_IMPORT_FAILED` | The imported snapshot was not indexed. |
| `SNAPSHOT_RESTORE_UNSAFE_PATH` | The restore target path is unsafe. |
| `SNAPSHOT_PASSWORD_INVALID` | The snapshot decryption password is incorrect. |

## MCP

| Code | Description |
| --- | --- |
| `MCP_TOKEN_NAME_REQUIRED` | An MCP token name is required. |
| `MCP_TOKEN_PERMISSION_INVALID` | MCP token permission must be read or write. |
| `MCP_TOKEN_EXPIRY_INVALID` | The MCP token expiry is invalid. |
| `MCP_TOKEN_NOT_FOUND` | The MCP token does not exist. |
| `MCP_AUDIT_RANGE_INVALID` | The audit cleanup time range is invalid. |
