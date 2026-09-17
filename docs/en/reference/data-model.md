# Data Model

This page describes the core domain objects in business terms.

## Config

A config is the root object of a Mesh.

| Field | Description |
| --- | --- |
| `id` | Config ID, such as `cfg_xxx`. |
| `name` | Config name; also affects generated interface names. |
| `virtual_subnet` | Mesh virtual subnet. |
| `default_listen_port` | Default listen port for new endpoints. |
| `default_mtu` | Default MTU. |
| `default_dns` | Default DNS. |
| `auto_sync` | Controls only the default auto-sync value for newly created endpoints. |
| `tunnel_protocol` | `wireguard` or `amneziawg_2`. |
| `awg_s1..awg_s4` | Config-level AmneziaWG S parameters. |
| `awg_h1..awg_h4` | Config-level AmneziaWG H parameters. |

## Node

An endpoint represents a device that joins the Mesh.

| Field | Description |
| --- | --- |
| `id` | Endpoint ID, such as `node_xxx`. |
| `config_id` | Owning config. |
| `name` | Endpoint name. |
| `ipv4_address` | Public IPv4 address or hostname. |
| `ipv6_address` | Public IPv6 address or hostname. |
| `listen_port` | Endpoint listen port. |
| `virtual_ip` | Mesh virtual IP. |
| `node_type` | `dynamic` or `static`. |
| `auto_sync` | Whether automatic synchronization is allowed. |
| `pre_up/post_up/pre_down/post_down` | Lifecycle commands. |
| `awg_jc/awg_jmin/awg_jmax` | Endpoint-local AmneziaWG junk parameters. |
| `awg_i1..awg_i5` | AmneziaWG CPS decoy-packet parameters. |

## PeerLink

A Mesh pair is represented by directional records. A bidirectional Mesh pair contains forward and reverse records with the same `link_group_id`.

| Field | Description |
| --- | --- |
| `local_node_id` | Local endpoint. |
| `peer_node_id` | Peer endpoint. |
| `allowed_ips` | AllowedIPs written to the Peer. |
| `persistent_keepalive` | PersistentKeepalive. |
| `preshared_key` | Optional PSK. |
| `endpoint_mode` | `auto`, `manual`, or `none`. |
| `endpoint_ref_family` | `ipv4` or `ipv6` for an automatic Endpoint. |
| `endpoint_port_mode` | Use the peer listen port or a manual port. |

## NodeConfigState

Synchronization state has three layers:

- `desired`: target state generated from current system data.
- `staged`: synchronized state waiting for client delivery.
- `confirmed`: state that the client has confirmed as applied.

## EndpointRuntimeStatus

Runtime state records online, tunnel, and synchronization state for dynamic endpoints.

The backend runtime projection is authoritative for online state. An explicit offline signal always marks the endpoint offline; otherwise any valid heartbeat, probe, or control-channel signal can keep it online.

## PortForwardRule

Port-forward rules are managed by the tool.

| Field | Description |
| --- | --- |
| `from_node_id` | From endpoint: where the service actually exists. |
| `from_port` | From port: where the service actually listens. |
| `to_node_id` | To endpoint: accepts incoming traffic and owns the lifecycle commands. |
| `to_port` | To port: the externally exposed access port. |
| `to_platform` | `linux` or `darwin`. |
| `protocol` | `tcp`, `udp`, or `all`. |
