# First Mesh

A mesh usually contains one config and multiple nodes. The config defines shared network rules, nodes represent real client endpoints, and peer links decide how nodes connect to each other.

## 1. Create a config

After opening the console, create a config first.

Key fields:

- Name: identifies the network in the console.
- Virtual subnet: virtual IPs are assigned from this subnet.
- Default listen port: the default WireGuard listen port for new nodes.
- Default DNS: DNS written into generated client configs.
- Protocol: `WireGuard` or `AmneziaWG 2.0`.

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

## Next steps

- To generate topologies automatically, read [Quick Mesh](/en/usage/quick-mesh).
- To learn about clients, read [Client Download and Binding](/en/usage/client).
- For deployment details, read [Deploy](/en/deploy/).
