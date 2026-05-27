# AI Integration

AI integration exposes WG Free Mesh to AI tools that support MCP. After setup, AI can query system state, inspect nodes, create download links, and run limited write operations after your confirmation.

## Create a Token

Open the console:

```text
Tool List -> Other -> AI Integration
```

Create an MCP Token:

- Choose `read` if the AI only needs to query system state.
- Choose `write` if the AI should create configs, run quick mesh, or generate download links.
- Set an expiration time.
- Copy the generated token.

A `write` token does not let AI silently change the system. Operations that affect business state still require confirmation in the MCP client.

## MCP Endpoint

The MCP endpoint is your system URL plus `/mcp`.

Default local Docker URL:

```text
http://localhost:8000/mcp
```

Production example:

```text
https://wfm.example.com/mcp
```

Authentication uses an HTTP header:

```http
Authorization: Bearer <mcp-token>
```

If your AI tool has an MCP configuration UI, fill in:

| Field | Value |
| --- | --- |
| Name | `wfm` |
| Type / Transport | HTTP / Streamable HTTP |
| URL | `http://localhost:8000/mcp` or `https://wfm.example.com/mcp` |
| Header | `Authorization: Bearer <mcp-token>` |

If the tool uses JSON configuration, the shape is commonly similar to:

```json
{
  "mcpServers": {
    "wfm": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer wfm_mcp_xxx"
      }
    }
  }
}
```

Different clients may use slightly different field names. The important parts are the URL and Bearer token.

## First Test

After setup, start with a read-only check:

```text
You are connected to the WG Free Mesh MCP server. First read wfm://help/overview and wfm://help/tool-index, then tell me what capabilities are available. Do not perform any write operation.
```

Then read system status:

```text
Use WFM MCP to inspect the current system status. List config count, node count, online node count, and MQTT status.
```

If both requests return useful content, the MCP connection is working.

## Useful Prompts

Check status:

```text
Check which WG Free Mesh nodes are offline. Group them by config and explain which status fields you used.
```

Inspect configs:

```text
List all configs and tell me each config's protocol, virtual subnet, node count, and mesh pair count.
```

Create a client download link:

```text
Create a Windows amd64 client download link. If you need me to choose a build target, ask me.
```

Export an existing snapshot:

```text
Export the latest existing snapshot and return the download URL. Do not create a new snapshot and do not restore anything.
```

Evaluate quick mesh:

```text
Check whether config mesh-main is ready for Free Mesh generation. First list which mesh pairs would be deleted and recreated. Do not execute it yet.
```

Run a write operation:

```text
Generate Free Mesh for config mesh-main and enable PSK. Show me the confirmation summary first, then continue only after I approve.
```

Create a config:

```text
Create a WireGuard config named office-mesh with virtual subnet 10.77.0.0/24 and default listen port 51820.
```

These prompts can be used with Claude Code, OpenClaw, or other MCP-capable clients. Whether write operations show a confirmation dialog depends on the client's MCP interaction support.

## Download URLs

Client downloads, bulk config downloads, and snapshot export do not transfer file bytes through MCP.

MCP returns a download URL that is valid for 5 minutes. Opening the URL triggers a file download. The URL is scoped to that one file only.

## Audit

The AI integration page shows MCP audit logs. You can search by:

- Time.
- Token name.
- Endpoint or tool name.

You can also clean audit logs by time range.

When you need to know what AI did, check the audit logs first. Write operations record an impact summary.

## Do Not Use AI for These

These actions must stay in the console:

- Create snapshots.
- Import snapshots.
- Restore snapshots.
- Delete snapshots.
- Enter administrator passwords.
- Enter snapshot passwords.

AI can export a download URL for an existing snapshot, but it cannot handle snapshot passwords or restore data.

## Troubleshooting

### MCP Cannot Connect

Check:

1. The URL is `/mcp`, not `/api/v1/...`.
2. The header is `Authorization: Bearer <mcp-token>`.
3. The access origin is allowed by the system. In production, use the URL configured as `WFM_PUBLIC_ORIGIN`.

### AI Says It Has No Write Permission

The token is a `read` token. Create a `write` token for write operations.

### A Write Operation Did Not Execute

Write operations require MCP client confirmation support. Parameter elicitation is not execution confirmation. The backend writes only after confirmation is completed.

For the complete resource and tool list, see [MCP Reference](/en/reference/mcp).
