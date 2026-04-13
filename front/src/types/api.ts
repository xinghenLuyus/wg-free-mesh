export interface ApiResponse<T> {
  success: boolean
  data: T
}

export interface ApiErrorBody {
  code: string
  message: string
  detail: Record<string, unknown>
}

export interface ApiErrorResponse {
  success: false
  error: ApiErrorBody
}

export interface SessionRead {
  authenticated: boolean
  username: string
  display_name: string
}

export interface ConfigRead {
  id: string
  name: string
  description: string
  enabled: boolean
  virtual_subnet: string
  default_listen_port: number
  default_mtu: number | null
  default_dns: string | null
  auto_sync: boolean
  node_count: number
  dynamic_node_count: number
  created_at: string
  updated_at: string
}

export interface ConfigOverviewRead {
  config: ConfigRead
  stats: {
    total_nodes: number
    dynamic_nodes: number
    static_nodes: number
    online_nodes: number
    pending_sync_nodes: number
    peer_links: number
  }
  runtime_snapshot: RuntimeSnapshotItem[]
  sync_status: SyncStatusRead[]
}

export interface NodeRead {
  id: string
  config_id: string
  name: string
  ipv4_address: string | null
  ipv6_address: string | null
  listen_port: number | null
  virtual_ip: string | null
  mtu: number | null
  dns: string | null
  auto_sync: boolean
  node_type: 'dynamic' | 'static'
  public_key: string
  private_key: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface PeerLinkRead {
  id: string
  config_id: string
  local_node_id: string
  peer_node_id: string
  link_group_id: string
  direction: 'forward' | 'reverse'
  enabled: boolean
  allowed_ips: string
  persistent_keepalive: number | null
  preshared_key: string | null
  endpoint_mode: 'none' | 'auto' | 'manual'
  endpoint_ref_family: 'ipv4' | 'ipv6' | 'domain' | null
  endpoint_manual_host: string | null
  endpoint_port_mode: 'ref_peer_listen_port' | 'manual'
  endpoint_manual_port: number | null
  notes: string
  created_at: string
  updated_at: string
}

export interface MeshValidationRead {
  valid: boolean
  messages: string[]
}

export interface WgPreviewRead {
  node_id: string
  node_name: string
  content: string
  sha256: string
}

export interface SyncStatusRead {
  node_id: string
  node_name: string
  node_type: 'dynamic' | 'static'
  auto_sync: boolean
  desired_version: number
  staged_version: number
  confirmed_version: number
  desired_sha256: string
  staged_sha256: string
  confirmed_sha256: string
  reported_local_sha256: string
  reported_local_version: number
  status: string
  runtime_status: string
}

export interface RuntimeSnapshotItem {
  node_id: string
  node_name: string
  node_type: 'dynamic' | 'static'
  online: boolean
  connectivity_state: string
  wg_running: boolean
  wg_runtime_state: string
  config_sync_state: string
  server_apply_status: string
  peers_online: number
  peers_total: number
  last_seen: string | null
  last_probe_sent_at: string | null
  last_probe_ack_at: string | null
}

export interface ControlLogRead {
  id: string
  request_id: string
  config_id: string
  node_id: string
  action: string
  status: string
  requested_by: string
  summary: string
  detail: string
  requested_at: string
  ack_at: string | null
  created_at: string
  updated_at: string
}

export interface EndpointStatusRead {
  node: NodeRead
  runtime: {
    online: boolean
    connectivity_state: string
    wg_running: boolean
    wg_runtime_state: string
    config_sync_state: string
    peers_online: number
    peers_total: number
    last_seen: string | null
    last_probe_sent_at: string | null
    last_probe_ack_at: string | null
    last_control_channel_seen_at: string | null
    last_config_sync_error: string
    last_connectivity_reason: string
    client_downloaded: boolean
    client_downloaded_at: string | null
  }
  config_state: {
    desired_version: number
    staged_version: number
    confirmed_version: number
    desired_sha256: string
    staged_sha256: string
    confirmed_sha256: string
    reported_local_sha256: string
    reported_local_version: number
    status: string
    server_apply_status: string
  }
  last_control: ControlLogRead | null
}

export interface MqttSettingsRead {
  host: string
  port: number
  tls: boolean
  username: string
  password: string
}

export interface SnapshotRead {
  id: string
  name: string
  path: string
  size: number
  note: string
  created_at: string
}

export interface HealthRead {
  status: string
  service: string
  version: string
  timestamp: string
}

export interface SystemStatusRead {
  summary: {
    configs: number
    nodes: number
    dynamic_nodes: number
    online_nodes: number
    pending_sync_nodes: number
  }
  services: {
    database: string
    mqtt: string
    wireguard: string
  }
  timestamp: string
}

export interface RealtimeEvent<T = Record<string, unknown>> {
  type: string
  timestamp: string
  payload: T
}
