import type { NodeRead } from '@/types/api'

export function toNodeUpdatePayload(node: NodeRead, overrides: Partial<NodeRead> = {}) {
  const next = { ...node, ...overrides }
  return {
    name: next.name,
    ipv4_address: next.ipv4_address,
    ipv6_address: next.ipv6_address,
    listen_port: next.listen_port,
    virtual_ip: next.virtual_ip,
    mtu: next.mtu,
    dns: next.dns,
    auto_sync: next.auto_sync,
    enabled: next.enabled,
    node_type: next.node_type,
    public_key: next.public_key,
    private_key: next.private_key,
    tags: next.tags,
  }
}

export function normalizeTags(tags: string[]) {
  return Array.from(new Set(tags.map((tag) => tag.trim()).filter(Boolean))).sort((left, right) =>
    left.localeCompare(right),
  )
}
