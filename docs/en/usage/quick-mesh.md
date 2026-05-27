# Quick Mesh

Quick Mesh automatically generates mesh pairs under the selected config. It is useful when nodes change and the topology needs to be rebuilt quickly.

Before running it, note that Quick Mesh deletes existing mesh pairs under the config and then regenerates them according to the selected mode. The page blocks interaction while generation is running to avoid duplicate operations during bulk delete and create.

## Preflight Checks

Quick Mesh checks whether the selected config and nodes satisfy the chosen mode:

- Nodes that need public access must have public IPv4 or IPv6.
- Gateway mode only allows nodes with public addresses to be selected as gateways.
- Full Mesh requires all participating nodes to have public addresses.
- Free Mesh selects all public nodes as gateways by default and allows manual adjustment.

If the left side shows unresolved issues, fix them before running Quick Mesh.

## Gateway Network

Gateway network is for one public node serving multiple leaf nodes.

In this mode:

- The Gateway node creates mesh pairs with other nodes.
- Leaf nodes do not need public addresses.
- Leaf node `AllowedIPs` should cover the entire virtual subnet, so traffic can reach the whole mesh through the Gateway.

This mode is best for "one cloud server plus home, office, or edge devices".

## Full Mesh

Full Mesh is for cases where all nodes have public entrypoints.

In this mode:

- All participating nodes connect to each other.
- Every node needs public IPv4 or IPv6.
- Each mesh pair usually only needs the peer virtual IP in `AllowedIPs`.

Full Mesh has the most direct paths, but the number of mesh pairs grows quickly as nodes increase.

## Free Mesh

Free Mesh combines multiple Gateway nodes into a backbone network while leaf nodes attach under selected gateways.

In this mode:

- Gateway nodes are fully connected.
- Leaf nodes attach to specified gateways.
- Leaf nodes may or may not have public addresses.
- Generated `AllowedIPs` keep all nodes mutually reachable.

This mode fits real mixed networks: some nodes act as backbone routers, some only join the network, but the whole mesh remains reachable.

## PSK

Mesh generation can enable preshared keys.

When enabled, every mesh pair receives a PSK. This improves key-material resilience, but regenerated mesh pairs must be pushed to clients again.

## After Generation

After generation, return to the config or node control page and push config. Online clients can receive config remotely. Offline clients must sync after reconnecting or be handled manually.
