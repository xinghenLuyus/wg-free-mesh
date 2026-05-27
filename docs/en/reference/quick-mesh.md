# Quick Mesh

Quick Mesh deletes existing peer links under the selected config and regenerates them.

## Modes

- `hub_spoke`: one gateway node and leaf nodes.
- `full_mesh`: all eligible public nodes connect directly.
- `free_mesh`: multiple gateways form a backbone, leaves attach to gateways.

## AllowedIPs

In gateway mode, leaf-to-gateway links use the full config subnet so leaves can reach the whole mesh through the gateway.

In Free Mesh, gateways connect to each other, gateway-to-leaf links use leaf virtual IPs, and leaf-to-gateway links use the full subnet.
