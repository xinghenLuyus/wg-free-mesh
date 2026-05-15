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

export interface AuthStateRead {
  setup_required: boolean
  authenticated: boolean
  username: string
  display_name: string
  expires_at: string | null
}

export interface TokenSessionRead extends AuthStateRead {
  access_token: string
  token_type: 'bearer'
}

export type AppLocale = 'zh-CN' | 'en-US'
export type AppThemeMode = 'system' | 'light' | 'dark'

export interface UiSettingsRead {
  locale: AppLocale
  theme_mode: AppThemeMode
}

export interface DownloadTokenRead {
  access_token: string
  token_type: 'download'
  expires_at: string
  download_path: string
  filename: string
}

export interface DownloadOptionRead {
  value: string
  label: string
  available?: boolean
  description?: string
}

export interface ClientDownloadOptionsRead {
  sources: DownloadOptionRead[]
  systems: DownloadOptionRead[]
  architectures: DownloadOptionRead[]
  defaults: {
    source: 'local_build' | 'github_release'
    goos: 'windows' | 'linux' | 'darwin'
    goarch: 'amd64' | 'arm64'
  }
  version: string
}

export interface ClientArtifactRead {
  artifact_id: string
  filename: string
  download_path: string
  source: 'local_build' | 'github_release'
  goos: 'windows' | 'linux' | 'darwin'
  goarch: 'amd64' | 'arm64'
  version: string
  cached: boolean
}

export interface ConfigBulkOptionConfigRead {
  id: string
  name: string
  enabled: boolean
  node_count: number
  dynamic_node_count: number
  disabled_node_count: number
}

export interface ConfigBulkOptionNodeRead {
  id: string
  name: string
  node_type: 'dynamic' | 'static'
  virtual_ip: string | null
  auto_sync: boolean
  can_download: boolean
  staged_version: number
  staged_sha256: string
  sync_status: string
}

export interface ConfigBulkOptionsRead {
  configs: ConfigBulkOptionConfigRead[]
  nodes: ConfigBulkOptionNodeRead[]
}

export interface ConfigBulkPackageRead {
  package_id: string
  filename: string
  download_path: string
  config_id: string
  config_name: string
  node_count: number
}

export type SessionRead = AuthStateRead

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
  online_node_count: number
  offline_node_count: number
  disabled_node_count: number
  topology_invalid: boolean
  topology_error_count: number
  created_at: string
  updated_at: string
}

export interface ChangeHintRead {
  code: string
  level: 'info' | 'warning'
  count?: number
  cleared_keepalive_count?: number
}

export interface ConfigMutationRead extends ConfigRead {
  change_hints: ChangeHintRead[]
  affected_node_ids: string[]
}

export interface ConfigOverviewNodeCardRead {
  id: string
  name: string
  node_type: 'dynamic' | 'static'
  enabled: boolean
  virtual_ip: string | null
  ipv4_address: string | null
  ipv6_address: string | null
  tags: string[]
  created_at: string
  online: boolean
  peers_total: number
  mesh_error: boolean
}

export interface TopologySummaryRead {
  valid: boolean
  error_count: number
  invalid_node_count: number
  invalid_node_ids: string[]
  errors: string[]
}

export interface SystemTopologyInvalidConfigRead {
  config_id: string
  config_name: string
  error_count: number
  invalid_node_count: number
  errors: string[]
}

export interface SystemTopologySummaryRead {
  valid: boolean
  invalid_config_count: number
  invalid_node_count: number
  invalid_configs: SystemTopologyInvalidConfigRead[]
}

export interface ConfigOverviewRead {
  config: ConfigRead
  stats: {
    total_nodes: number
    dynamic_nodes: number
    static_nodes: number
    disabled_nodes: number
    online_nodes: number
    peer_links: number
  }
  nodes: NodeRead[]
  node_cards: ConfigOverviewNodeCardRead[]
  disabled_node_cards: ConfigOverviewNodeCardRead[]
  runtime_snapshot: RuntimeSnapshotItem[]
  sync_status: SyncStatusRead[]
  topology: TopologySummaryRead
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
  enabled: boolean
  node_type: 'dynamic' | 'static'
  public_key: string
  private_key: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface NodeMutationRead extends NodeRead {
  change_hints: ChangeHintRead[]
  affected_node_ids: string[]
}

export interface TagRead {
  name: string
  count: number
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
  endpoint_ref_family: 'ipv4' | 'ipv6' | null
  endpoint_manual_host: string | null
  endpoint_port_mode: 'ref_peer_listen_port' | 'manual'
  endpoint_manual_port: number | null
  notes: string
  created_at: string
  updated_at: string
}

export interface PeerLinkDirectionDraftRead {
  local_node_id: string
  peer_node_id: string
  allowed_ips: string
  persistent_keepalive: number | null
  endpoint_mode: 'auto'
  endpoint_ref_family: 'ipv4' | 'ipv6'
  endpoint_manual_host: string
  endpoint_port_mode: 'ref_peer_listen_port'
  endpoint_manual_port: number | null
  endpoint_summary: string
  keepalive_display: string
}

export interface PeerLinkDraftRead {
  local_node: NodeRead
  peer_node: NodeRead
  endpoint_ref_family: 'ipv4' | 'ipv6'
  forward: PeerLinkDirectionDraftRead
  reverse: PeerLinkDirectionDraftRead
  warnings: string[]
}

export interface MeshConnectionDirectionRead {
  link_id: string
  local_node_id: string
  peer_node_id: string
  allowed_ips: string
  persistent_keepalive: number | null
  endpoint_mode: 'none' | 'auto' | 'manual'
  endpoint_ref_family: 'ipv4' | 'ipv6' | null
  endpoint_manual_host: string | null
  endpoint_port_mode: 'ref_peer_listen_port' | 'manual'
  endpoint_manual_port: number | null
  endpoint_summary: string
  keepalive_display: string
}

export interface MeshConnectionRead {
  link_group_id: string
  peer_node: NodeRead
  enabled: boolean
  has_preshared_key: boolean
  preshared_key: string | null
  notes: string
  updated_at: string
  forward: MeshConnectionDirectionRead
  reverse: MeshConnectionDirectionRead | null
  integrity_status: 'healthy' | 'broken'
  integrity_message: string
  duplicate_enabled_pair: boolean
  duplicate_message: string
  readonly: boolean
  peer_disabled: boolean
}

export interface MeshWorkspaceRead {
  node: NodeRead
  connections: MeshConnectionRead[]
  readonly: boolean
  validation: MeshValidationRead
}

export interface MeshValidationRead {
  valid: boolean
  messages: string[]
  errors: string[]
  warnings: string[]
}

export interface WgPreviewRead {
  node_id: string
  node_name: string
  content: string
  sha256: string
}

export interface DownloadPackageRead {
  config_id: string
  node_id: string
  config_name: string
  node_name: string
  filename: string
  content: string
  download_path: string
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
  topology_valid: boolean
  topology_messages: string[]
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
  heartbeat_client_online: boolean
  heartbeat_wg_online: boolean
  detect_client_online: boolean
  detect_wg_online: boolean
  client_initialized: boolean
  client_presence_state: 'online' | 'dropped' | 'offline' | string
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
    heartbeat_client_online: boolean
    heartbeat_wg_online: boolean
    detect_client_online: boolean
    detect_wg_online: boolean
    last_config_sync_error: string
    last_connectivity_reason: string
    client_downloaded: boolean
    client_downloaded_at: string | null
  }
  client_state: {
    client_initialized: boolean
    client_platform?: string
    client_version?: string
    client_hostname?: string
    client_version_label?: string
    mqtt_username?: string
    mqtt_client_id?: string
    client_presence_state: 'online' | 'dropped' | 'offline' | string
    boot_id?: string
    session_id?: string
    last_heartbeat_at?: string | null
    last_detect_ack_at?: string | null
    last_reachable_at?: string | null
    last_offline_at?: string | null
    last_will_at?: string | null
    last_event?: string
    last_event_at?: string | null
  }
  mqtt_service: {
    enabled: boolean
    connected: boolean
    status: string
    last_error?: string
    last_connected_at?: string | null
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
    wg_config_version_state: 'latest' | 'pending' | string
  }
  last_control: ControlLogRead | null
}

export interface ClientBindCommandRead {
  command: string
  token: string
  expires_at: string
}

export interface MqttSettingsRead {
  host: string
  port: number
  tls: boolean
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
  timezone: string
  dev_test_api_enabled: boolean
}

export interface SystemStatusRead {
  summary: {
    configs: number
    nodes: number
    dynamic_nodes: number
    online_nodes: number
  }
  sync: {
    issue_count: number
    issues: Array<{
      config_id: string
      config_name: string
      node_id: string
      node_name: string
      node_type: 'dynamic' | 'static' | string
      status: string
      topology_valid: boolean
      messages: string[]
    }>
  }
  topology: SystemTopologySummaryRead
  services: {
    database: string
    mqtt: string
    wireguard: string
  }
  timestamp: string
}

export interface RealtimeEvent<T = Record<string, unknown>> {
  id?: string
  type: string
  timestamp: string
  payload: T
}

export interface SystemClockSyncPayload {
  timestamp: string
  timezone?: string
}

export interface SystemTimezoneRead {
  timezone: string
}

export interface SystemStatusSnapshotPayload extends SystemStatusRead {}

export interface EndpointStatusUpdatedPayload {
  config_id: string
  node_id: string
  status: EndpointStatusRead | null
}

export interface RuntimeNodeUpdatedPayload {
  config_id: string
  node_id: string
  runtime: EndpointStatusRead['runtime']
  config_state?: EndpointStatusRead['config_state']
}

export interface ControlLogEventPayload {
  config_id: string
  node_id: string
  log: ControlLogRead
}

export interface ConfigListUpdatedPayload {
  configs: ConfigRead[]
}

export interface ConfigOverviewUpdatedPayload {
  config_id: string
  overview: ConfigOverviewRead
  tags: TagRead[]
}

export interface NodeWorkspaceUpdatedPayload {
  config_id: string
  node_id: string
  workspace: {
    config: ConfigRead | null
    node: NodeRead
    endpoint_status: EndpointStatusRead | null
    tags: TagRead[]
  }
}

export interface NodeApplyUpdatedPayload {
  config_id: string
  node_id: string
  sync_status: SyncStatusRead
  preview: WgPreviewRead
  applied: {
    content: string
    exists: boolean
    node_name: string
    node_type: string
    desired_version: number
    staged_version: number
  }
}

export interface MeshWorkspaceUpdatedPayload {
  config_id: string
  node_id: string
  workspace: MeshWorkspaceRead
  nodes: NodeRead[]
}

export interface SnapshotListUpdatedPayload {
  snapshots: SnapshotRead[]
}

export interface MqttSettingsUpdatedPayload {
  mqtt: MqttSettingsRead
}
