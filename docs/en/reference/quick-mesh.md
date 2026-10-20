# Quick Mesh

Quick Mesh deletes the existing Mesh pairs in the selected config and regenerates them using the chosen mode.

## Common Parameters

| Field | Description |
| --- | --- |
| `mode` | `hub_spoke`, `full_mesh`, or `free_mesh`. |
| `endpoint_ref_family` | Use the `ipv4` or `ipv6` public entry. |
| `use_preshared_key` | Whether generated Mesh pairs use a PSK. |
| `allow_linux_forwarding` | Defaults to `false`. Append missing iptables lifecycle commands to all selected gateways in Gateway / Free Mesh. Ignored for Full Mesh. Gateways must run Linux with iptables installed. |

When `allow_linux_forwarding` is enabled, the commands below are added to gateway `post_up` and `post_down` lists respectively, unless an identical command already exists after trimming surrounding whitespace. They remain ordinary editable lifecycle commands. Disabling the option or changing node roles does not remove existing commands. Apply the config to take effect.

```ini
PostUp = iptables -I FORWARD 1 -i %i -o %i -j ACCEPT
PostDown = iptables -D FORWARD -i %i -o %i -j ACCEPT
```

## Gateway-node Network

`hub_spoke` uses one gateway endpoint as the center.

Requirements:

- At least two enabled endpoints.
- The gateway must be enabled.
- The gateway must have a public entry for the selected address family.

AllowedIPs rules:

- Gateway to leaf: use the leaf virtual IP.
- Leaf to gateway: use the entire config virtual subnet so leaves communicate through the gateway.

## Full Mesh

`full_mesh` directly connects every pair of enabled endpoints that has a public entry.

Requirements:

- At least two enabled endpoints.
- Every participating endpoint must have a public entry for the selected address family.

AllowedIPs normally contains the peer virtual IP.

## Free Mesh

`free_mesh` allows multiple gateways to form a full-mesh backbone, with each leaf attached to one gateway.

Requirements:

- At least one gateway.
- Every gateway must be an enabled endpoint.
- Every gateway must have a public entry for the selected address family.
- Every enabled endpoint must be assigned as a gateway or a leaf.
- An endpoint cannot be both a gateway and a leaf.
- A leaf's gateway must belong to the selected gateway set.

AllowedIPs rules:

- Gateway to gateway: use the peer virtual IP and form the backbone.
- Leaf to its gateway: use the entire config virtual subnet so the leaf can reach the full network.
- Gateway to its direct leaf: use the leaf virtual IP.
- Other leaves are reached through the gateway backbone.
