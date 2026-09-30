# Configs and Nodes

A config is the container for a mesh network. A node is a device or client instance that joins that network.

## What a Config Defines

A config defines the base rules of one mesh network:

- Virtual subnet.
- Default listen port.
- Default DNS.
- Default MTU.
- Default behavior for newly created nodes.
- Protocol type: WireGuard or AmneziaWG.

After creation, these base parameters can still be edited. Changes affect generated config content, but they do not override each node's own switches and advanced settings.

When opening a config or node page, loading areas keep the page layout in place. If the config's advanced settings contain many parameters, scroll within the dialog to review them.

## Protocol Choice

The default protocol is standard WireGuard. It fits most private networks, cloud servers, and cross-region mesh setups.

When AmneziaWG is selected, the config also maintains mesh-level parameters:

Select AWG 1.5, 2.0, or 3.1, then review the prefilled parameters for that version. Protocol selection, version changes, and random generation update the page draft only; they take effect together on save. Canceling leaves the actual config unchanged. When switching AWG versions, historical parameters remain in the database but are omitted from config output for versions that do not support them. See [AWG Protocol Compatibility](/en/help/awg-compatibility) for version-specific parameters and toolchain requirements.

- `S1` to `S4`.
- `H1` to `H4`.

These parameters identify the Mesh protocol and must remain consistent within one config. Advanced settings provides a shared direction and intensity selector to generate config parameters and independent parameters for all existing endpoints together. Generation updates the draft only. Every field remains editable or clearable; save to apply. Existing shared keys are not regenerated.

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
