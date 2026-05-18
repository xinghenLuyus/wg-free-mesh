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
    pre_up: next.pre_up,
    post_up: next.post_up,
    pre_down: next.pre_down,
    post_down: next.post_down,
    awg_jc: next.awg_jc,
    awg_jmin: next.awg_jmin,
    awg_jmax: next.awg_jmax,
    awg_i1: next.awg_i1,
    awg_i2: next.awg_i2,
    awg_i3: next.awg_i3,
    awg_i4: next.awg_i4,
    awg_i5: next.awg_i5,
  }
}

export function normalizeTags(tags: string[]) {
  return Array.from(new Set(tags.map((tag) => tag.trim()).filter(Boolean))).sort((left, right) =>
    left.localeCompare(right),
  )
}
