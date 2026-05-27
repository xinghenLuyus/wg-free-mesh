# Usage

WG Free Mesh puts the common work of a WireGuard network into one console: create configs, add nodes, generate mesh links, download clients, push config, check status, and make backups.

For a few nodes, handwritten configs can still work. Once the network grows, addresses, ports, PSKs, AllowedIPs, client status, and config sync become easy to lose track of. WG Free Mesh is built to remove that repetitive work.

## Start with a Config

A network starts with a config. It defines the virtual subnet, default port, DNS, MTU, and whether the network uses standard WireGuard or AmneziaWG 2.0.

Then add devices as nodes. A node stores virtual IP, public address, tags, client binding state, and advanced parameters. Public nodes can participate in more automatic topology modes, while private nodes can still join as leaves.

Continue: [Configs and Nodes](/en/usage/configs)

## Bring Clients Online

The download page builds client packages for the selected operating system and architecture. The node control page provides the bind command. After binding, the client can receive config and control commands.

Once a client is online, the console can push config, start or stop tunnels, inspect WireGuard / AmneziaWG state, and use logs to troubleshoot connection issues.

Continue: [Client and Control](/en/usage/client)

## Generate Mesh Links

Quick Mesh rebuilds mesh pairs in bulk. It is useful after nodes have changed and the topology needs to be refreshed.

It currently supports Gateway, Full Mesh, and Free Mesh. The system checks whether nodes have public addresses before generating AllowedIPs and mesh pairs.

Continue: [Quick Mesh](/en/usage/quick-mesh)

## Expose Internal Services

Port forwarding exposes a service port on a From node through a selected port on a To node. It is useful when an internal mesh service needs to be reachable through another node.

This feature depends on lifecycle commands on the To node, so the To node should currently be Linux or macOS.

Continue: [Port Forwarding](/en/usage/port-forward)

## Back Up and Migrate

Snapshots are application-level backups. They do not depend on a specific database file, so they can migrate data from SQLite to PostgreSQL or the other way around.

Snapshots include business data but not the administrator password. Before restoring, export the current state first if a rollback path is needed.

Continue: [Backups](/en/usage/backups)

## Connect AI Tools

AI integration uses MCP to expose controlled capabilities. It is best for queries, troubleshooting assistance, download link generation, and limited write operations after confirmation.

High-risk actions, such as snapshot import and restore, still require manual operation in the console.

Continue: [AI Integration](/en/ai/)

## When You Need Details

Usage pages explain how to use features and where their boundaries are. Fields, APIs, MCP tools, error codes, and data models live in [Reference](/en/reference/).
