# Data Model

## Config

A config is the root object of one mesh. It stores subnet, default port, DNS, protocol, and config-level AWG parameters.

## Node

A node represents a device. It can be `dynamic` for client-managed endpoints or `static` for manually managed endpoints.

## PeerLink

A bidirectional peer link group contains two directional `PeerLink` records with the same `link_group_id`.

## NodeConfigState

Generated state is tracked as `desired`, `staged`, and `confirmed`.

## EndpointRuntimeStatus

Runtime state tracks online status, WireGuard/AmneziaWG state, config sync state, heartbeat, detect, and control-channel activity.

## PortForwardRule

A managed port-forward rule exposes a service port on a From node through a selected port on a To node. From is the source side: the node and port where the service exists. To is the destination side: the node and port users connect to. The To node accepts traffic, owns generated lifecycle hooks, and forwards traffic to the From node.
