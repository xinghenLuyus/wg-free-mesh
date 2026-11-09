import type { MeshConnectionRead } from './api'

export interface TopologyNode {
  id: string
  name: string
  node_type: 'dynamic' | 'static'
  enabled: boolean
  virtual_ip: string | null
  ipv4_address: string | null
  ipv6_address: string | null
  tags: string[]
  endpoint_state: 'offline' | 'not_started' | 'online' | null
  wg_runtime_state: string | null
  config_sync_state: string | null
}
export interface TopologyDirection {
  link_id: string
  local_node_id: string
  peer_node_id: string
  allowed_ips: string
  persistent_keepalive: number | null
  endpoint_summary: string
  endpoint_ref_family: string | null
}
export interface TopologyConnection {
  id: string
  source: string
  target: string
  enabled: boolean
  integrity: boolean
  validation_errors: string[]
  has_preshared_key: boolean
  forward: TopologyDirection | null
  reverse: TopologyDirection | null
  health: MeshConnectionRead['health']
}
export interface TopologyBoard {
  config: { id: string; name: string; enabled: boolean; tunnel_protocol: string; awg_version: string | null }
  nodes: TopologyNode[]
  connections: TopologyConnection[]
  issues: { group_id: string; reason: string }[]
  generated_at: string
}
