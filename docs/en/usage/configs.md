# Configs and Nodes

A config is the container for a mesh network. A node is a device or client instance that joins that network.

## What a Config Defines

A config defines the base rules of one mesh network:

- Virtual subnet.
- Default listen port.
- Default DNS.
- Default MTU.
- Default behavior for newly created nodes.
- Protocol type: WireGuard or AmneziaWG 2.0.

After creation, these base parameters can still be edited. Changes affect generated config content, but they do not override each node's own switches and advanced settings.

## Protocol Choice

The default protocol is standard WireGuard. It fits most private networks, cloud servers, and cross-region mesh setups.

When AmneziaWG 2.0 is selected, the config also maintains mesh-level parameters:

- `S1` to `S4`.
- `H1` to `H4`.

These parameters are part of the protocol identification rules of the mesh and must stay consistent within the same config. The page allows leaving them empty for random generation or randomizing fields individually.

Node-level AmneziaWG parameters are maintained in node advanced settings: `Jc`, `Jmin`, `Jmax`, and `I1` to `I5`.

## What a Node Stores

A node usually includes:

- Name and tags.
- Virtual IP.
- Public IPv4 / IPv6.
- Whether client binding is allowed.
- Whether automatic sync is enabled.
- Online state and client version.
- Lifecycle commands and advanced protocol parameters.

A node can be a public node or a leaf node that is only reachable inside the mesh. Quick Mesh uses public address availability to decide whether a node can participate as a Gateway or Full Mesh member.

## Online State

Node online state is calculated from multiple signals. If any valid online signal exists, the node can be considered online. If an explicit offline signal is received, the system marks the node offline immediately.

Common online signals include:

- MQTT connection state.
- Successful control command response.
- Recent client status report.

If MQTT is disabled at the deployment level, client binding and endpoint control are disabled system-wide, and related pages show that the feature is unavailable.

## Advanced Settings

Node advanced settings maintain two categories:

- Lifecycle commands: `PreUp`, `PostUp`, `PreDown`, `PostDown`.
- AmneziaWG local noise parameters.

Lifecycle commands are executed by `wg-quick` / `awg-quick`. The Windows WireGuard GUI toolchain does not provide equivalent hook behavior, so features that depend on lifecycle commands, such as port forwarding, normally require Linux or macOS as the target node.

## Deleting a Config

Deleting a config is a high-risk operation. It affects nodes, mesh pairs, bindings, and related business data under that config. Export a snapshot before doing it.
