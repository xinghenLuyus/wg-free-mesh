# First Mesh

A mesh usually contains one config and multiple nodes. The config defines shared network rules, nodes represent real client endpoints, and peer links decide how nodes connect to each other.

*A mesh contains multiple peer links. Each link defines the connection between two nodes.*

## 1. Create a config

After opening the console, create a config first.

Key fields:

- Name: identifies the network in the console.
- Virtual subnet: virtual IPs are assigned from this subnet.
- Default listen port: the default WireGuard listen port for new nodes.
- Default DNS: DNS written into generated client configs.
- Protocol: `WireGuard` or `AmneziaWG`.

If you are unsure, keep the default WireGuard protocol.

## 2. Add nodes

A node represents a device that joins the mesh.

Common fields:

- Name: identifies the device in the console.
- Virtual IP: the address used inside the mesh.
- Public IPv4 / IPv6: used by other nodes to connect to it.
- Listen port: the node's WireGuard listen port.
- Type: dynamic or static.

Dynamic nodes are suitable for WFM client binding and remote control. Static nodes are suitable when you only want to download configs and manage the device manually.

## 3. Generate peer links

After creating nodes, create the Mesh peer links.

You can choose either:

- Manual maintenance: useful for small networks or precise control over `AllowedIPs`, Endpoint, and PSK.
- Quick Mesh: useful for generating gateway, full mesh, or Free Mesh topologies in one action.

For the first run, Quick Mesh is usually easier. Before generation, the system will warn that it deletes existing peer links in the config and regenerates them.

## 4. Download and bind the client

For dynamic nodes, open the endpoint control page and follow the steps:

1. Download the client package for the target system and architecture.
2. Install the client service.
3. Run the bind command.

After binding succeeds, the node appears in runtime status in the console.

## 5. Push config

After peer links are generated, the system builds a WireGuard / AmneziaWG config for each node.

For bound dynamic nodes, push the config from the config apply page or endpoint control page. After delivery, the system records sync status and client confirmation.

## 6. Verify the network

Check:

- Whether the config overview reports topology errors.
- Whether nodes are online.
- Whether config apply status is in sync.
- Whether endpoint control logs contain failures.
- Whether nodes can reach each other through virtual IPs.

## Topology board

Click **Topology board** above the node list in a config to open all its nodes and direct Mesh relationships in a new tab. The board is read-only and does not edit configs.

Disabled nodes and connections remain visible, using dashed circular borders and dashed lines respectively. They can still be selected to view details. A dashed **Disabled** legend entry appears while any disabled nodes or connections exist.

Select a circular node for details and adjacent connections. Hover or select a thin connection to reveal both arrows and their separate AllowedIPs. Connection details include available observations from both ends, with handshakes and cumulative transfers. Static-to-static connections have no runtime health state. A recorded handshake does not guarantee current reachability of every business address.

Multiple Mesh pairs between the same endpoints appear as separate curves and can be selected independently. Connection numbers distinguish pairs between those endpoints; details also show their enabled status and Mesh pair ID. Only one Mesh pair between the same endpoints may be enabled.

Mesh validation errors use red lines, including duplicate enabled pairs, conflicting directions, or invalid endpoint configuration. Select a connection to see the cause. Offline clients or interrupted handshakes still use gray lines. The red validation legend appears only while errors exist.

Drag nodes or the canvas, scroll to zoom, and use **Fit view** to arrange the view. Positions and marker colors stay in the current browser, not in the database or snapshots. The board follows console language and light/dark themes, with no theme switch on the board itself. Hidden pages stop renewing active collection demand.

## Next steps

- To generate topologies automatically, read [Quick Mesh](/en/usage/quick-mesh).
- To learn about clients, read [Client Download and Binding](/en/usage/client).
- For deployment details, read [Deploy](/en/deploy/).
