# MCP

The MCP endpoint is `/mcp`.

```http
Authorization: Bearer <mcp-token>
```

## Resources

- `wfm://help/overview`
- `wfm://help/tool-index`
- `wfm://help/workflows`
- `wfm://schema/payloads`
- `wfm://system/status`
- `wfm://configs`

## Tool groups

- system
- configs
- nodes
- mesh
- sync and runtime
- tools
- port forwarding
- snapshots

Write tools require a `write` token and confirmation. Snapshot create, import, restore, delete, and snapshot passwords are intentionally not exposed through MCP.

Download-related MCP tools return 5-minute scoped URLs instead of file bytes.
