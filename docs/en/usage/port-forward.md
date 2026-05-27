# Port Forwarding

Port forwarding exposes a service port on a From node through a selected port on a To node.

From is the service source: the node where the real service exists. To is the forwarding entrypoint: the node users connect to. For example, forwarding From `10.8.0.2:80` to To `10.8.0.3:8080` means users connect to port `8080` on the To node, and the To node forwards traffic to port `80` on the From node.

In UI labels and system fields, From maps to source and To maps to destination:

- From node = source node.
- From port = source port, the real service port.
- To node = destination node.
- To port = destination port, the exposed access port.

## Protocols

Rules support:

- TCP.
- UDP.
- All traffic.

The protocol applies to the destination port exposed on the To node. TCP only forwards TCP, UDP only forwards UDP, and all traffic generates the corresponding rules.

## System Limits

Port forwarding is implemented through lifecycle commands on the To node, so the To node system must be selected explicitly.

Currently supported:

- Linux.
- macOS.

Windows is not supported as the To node because the Windows WireGuard GUI toolchain does not provide equivalent `wg-quick` hook behavior.

## Managed Rules

The port forwarding page lists managed rules around the "From xxx To xxx" reading pattern.

Read it as:

- From: where the service is.
- To: where the service is exposed.

Each rule can be temporarily disabled. When disabled, the status should show disabled and the notification should say that port forwarding has been disabled.

## Create a Rule

Creating a rule requires:

- Config.
- From node: the node where the real service exists.
- Source port: the service port on the From node.
- Protocol.
- To node: the node that accepts traffic and executes forwarding commands.
- Destination port: the port exposed on the To node.
- Destination system: the system type of the To node.

After creation, the system writes lifecycle commands to the To node. The To node must re-apply config before the rule takes effect.

## Delete a Rule

Lifecycle commands created by the port forwarding tool must be deleted from the port forwarding page.

The node advanced settings page can show these commands, but the delete button is disabled. This prevents partial manual deletion that would make the port forwarding page state diverge from the real commands.

## System Forwarding

Linux and macOS need IPv4 forwarding enabled to forward traffic. The client install process attempts to enable it. If that fails, it prints an error but does not block installation.
