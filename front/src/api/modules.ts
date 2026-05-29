import { request } from '@/api/client'
import type {
  ConfigMutationRead,
  ConfigOverviewRead,
  ConfigRead,
  ControlLogRead,
  ClientBindCommandRead,
  ClientArtifactRead,
  ClientDownloadOptionsRead,
  EndpointStatusRead,
  AppLocale,
  HealthRead,
  MeshValidationRead,
  MeshWorkspaceRead,
  MqttSettingsRead,
  NodeMutationRead,
  NodeRead,
  PeerLinkDraftRead,
  PeerLinkRead,
  AuthStateRead,
  DownloadTokenRead,
  UiSettingsRead,
  TokenSessionRead,
  SystemTimezoneRead,
  SnapshotRead,
  SyncStatusRead,
  SystemStatusRead,
  TagRead,
  RuntimeSnapshotItem,
  WgPreviewRead,
  DownloadPackageRead,
  ConfigBulkOptionsRead,
  ConfigBulkPackageRead,
  EndpointRefFamily,
  PortForwardRuleRead,
  QuickMeshGenerateRead,
  QuickMeshMode,
  McpAuditDeleteResult,
  McpAuditQuery,
  McpAuditRead,
  McpTokenRead,
} from '@/types/api'

function toQueryString(query: object) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query) as Array<[string, string | number | undefined]>) {
    if (value !== undefined && value !== '') {
      params.set(key, String(value))
    }
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const api = {
  authState: () => request<AuthStateRead>('/auth/state'),
  setup: (password: string, locale: AppLocale = 'zh-CN') =>
    request<TokenSessionRead>('/auth/setup', { method: 'POST', data: { password, locale } }),
  login: (username: string, password: string) =>
    request<TokenSessionRead>('/auth/login', { method: 'POST', data: { username, password } }),
  session: () => request<AuthStateRead>('/auth/session'),
  logout: () => request<{ message: string }>('/auth/logout', { method: 'POST' }),
  changePassword: (current_password: string, new_password: string) =>
    request<TokenSessionRead>('/auth/password', {
      method: 'POST',
      data: { current_password, new_password },
    }),

  health: () => request<HealthRead>('/system/health'),
  systemTimezone: () => request<SystemTimezoneRead>('/system/timezone'),
  systemStatus: () => request<SystemStatusRead>('/system/status'),

  configs: () => request<ConfigRead[]>('/configs'),
  configOverview: (configId: string) => request<ConfigOverviewRead>(`/configs/${configId}/overview`),
  createConfig: (payload: Record<string, unknown>) =>
    request<ConfigRead>('/configs', { method: 'POST', data: payload }),
  updateConfig: (configId: string, payload: Record<string, unknown>) =>
    request<ConfigMutationRead>(`/configs/${configId}`, { method: 'PUT', data: payload }),
  randomAwgConfig: () =>
    request<Record<string, number | string>>('/configs/awg/random', { method: 'POST' }),
  deleteConfig: (configId: string) =>
    request<{ message: string }>(`/configs/${configId}`, { method: 'DELETE' }),

  nodes: (configId: string) => request<NodeRead[]>(`/configs/${configId}/nodes`),
  node: (nodeId: string) => request<NodeRead>(`/nodes/${nodeId}`),
  createNode: (configId: string, payload: Record<string, unknown>) =>
    request<NodeRead>(`/configs/${configId}/nodes`, { method: 'POST', data: payload }),
  updateNode: (nodeId: string, payload: Record<string, unknown>) =>
    request<NodeMutationRead>(`/nodes/${nodeId}`, { method: 'PUT', data: payload }),
  deleteNode: (nodeId: string) =>
    request<{ message: string }>(`/nodes/${nodeId}`, { method: 'DELETE' }),
  tags: (configId: string) => request<TagRead[]>(`/configs/${configId}/tags`),
  createTag: (configId: string, name: string) =>
    request<TagRead>(`/configs/${configId}/tags`, { method: 'POST', data: { name } }),
  applyTagToNodes: (configId: string, tag: string, node_ids: string[]) =>
    request<NodeRead[]>(`/configs/${configId}/tags/apply`, {
      method: 'POST',
      data: { tag, node_ids },
    }),
  deleteTag: (configId: string, tag: string) =>
    request<{ message: string; removed_count: number }>(
      `/configs/${configId}/tags/${encodeURIComponent(tag)}`,
      { method: 'DELETE' },
    ),
  replaceNodeTags: (nodeId: string, tags: string[]) =>
    request<NodeRead>(`/nodes/${nodeId}/tags`, { method: 'PUT', data: { tags } }),
  removeTagFromNode: (nodeId: string, tag: string) =>
    request<NodeRead>(`/nodes/${nodeId}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' }),
  suggestIp: (configId: string) =>
    request<{ ip: string }>(`/configs/${configId}/nodes/suggest-ip`, { method: 'POST' }),
  validateIp: (configId: string, virtual_ip: string) =>
    request<{ valid: boolean; warning: string }>(`/configs/${configId}/nodes/validate-ip`, {
      method: 'POST',
      data: { virtual_ip },
    }),
  generateKeys: () => request<{ private_key: string; public_key: string }>('/nodes/keys/generate', { method: 'POST' }),
  randomAwgNode: () =>
    request<Record<string, number | string | null>>('/nodes/awg/random', { method: 'POST' }),

  peerLinks: (configId: string) => request<PeerLinkRead[]>(`/configs/${configId}/peer-links`),
  meshWorkspace: (configId: string, nodeId: string) =>
    request<MeshWorkspaceRead>(`/configs/${configId}/nodes/${nodeId}/mesh-workspace`),
  peerLinkDraft: (configId: string, nodeId: string, peerNodeId: string, endpointRefFamily: 'ipv4' | 'ipv6') =>
    request<PeerLinkDraftRead>(
      `/configs/${configId}/nodes/${nodeId}/peer-link-draft?peer_node_id=${encodeURIComponent(peerNodeId)}&endpoint_ref_family=${endpointRefFamily}`,
    ),
  createPeerLink: (configId: string, payload: Record<string, unknown>) =>
    request<PeerLinkRead[]>(`/configs/${configId}/peer-links`, { method: 'POST', data: payload }),
  updatePeerLinkGroup: (groupId: string, payload: Record<string, unknown>) =>
    request<PeerLinkRead[]>(`/peer-links/${groupId}`, { method: 'PUT', data: payload }),
  deletePeerLinkGroup: (groupId: string) =>
    request<{ message: string }>(`/peer-links/${groupId}`, { method: 'DELETE' }),
  generatePresharedKey: () =>
    request<{ preshared_key: string }>('/peer-links/psk/generate', { method: 'POST' }),
  validateMesh: (configId: string) =>
    request<MeshValidationRead>(`/configs/${configId}/mesh/validate`, { method: 'POST' }),
  quickGenerateMesh: (configId: string, payload: {
    mode: QuickMeshMode
    endpoint_ref_family: EndpointRefFamily
    hub_node_id?: string
    gateway_node_ids?: string[]
    leaf_assignments?: Record<string, string>
    use_preshared_key: boolean
  }) =>
    request<QuickMeshGenerateRead>(`/configs/${configId}/mesh/quick-generate`, { method: 'POST', data: payload, timeout: 120000 }),
  wgPreview: (configId: string, nodeId: string) =>
    request<WgPreviewRead>(`/configs/${configId}/nodes/${nodeId}/wg-preview`),

  syncStatuses: (configId: string) => request<SyncStatusRead[]>(`/configs/${configId}/sync-status`),
  nodeSyncStatus: (configId: string, nodeId: string) =>
    request<SyncStatusRead>(`/configs/${configId}/nodes/${nodeId}/sync-status`),
  readAppliedConf: (configId: string, nodeId: string) =>
    request<{ content: string; exists: boolean; node_name: string; node_type: string; desired_version: number; staged_version: number }>(
      `/configs/${configId}/nodes/${nodeId}/applied-conf`,
    ),
  downloadPackage: (configId: string, nodeId: string) =>
    request<DownloadPackageRead>(`/configs/${configId}/nodes/${nodeId}/download-package`),
  createDownloadToken: (configId: string, nodeId: string) =>
    request<DownloadTokenRead>(`/configs/${configId}/nodes/${nodeId}/download-token`, { method: 'POST' }),
  clientDownloadOptions: () => request<ClientDownloadOptionsRead>('/tools/download/client-options'),
  buildClientArtifact: (payload: { source: string; goos: string; goarch: string }) =>
    request<ClientArtifactRead>('/tools/download/client-artifacts/build', { method: 'POST', data: payload, timeout: 360000 }),
  createClientArtifactDownloadGrant: (payload: { source: string; goos: string; goarch: string }) =>
    request<ClientArtifactRead>('/tools/download/client-artifacts/download-grant', { method: 'POST', data: payload, timeout: 360000 }),
  downloadClientArtifact: (artifactId: string) =>
    request<Blob>(`/tools/download/client-artifacts/${artifactId}`, { responseType: 'blob', timeout: 120000 }),
  configBulkOptions: (configId?: string) =>
    request<ConfigBulkOptionsRead>(
      `/tools/download/config-bulk/options${configId ? `?config_id=${encodeURIComponent(configId)}` : ''}`,
    ),
  createConfigBulkPackage: (payload: { config_id: string; node_ids: string[] }) =>
    request<ConfigBulkPackageRead>('/tools/download/config-bulk/package', { method: 'POST', data: payload }),
  downloadConfigBulkPackage: (packageId: string) =>
    request<Blob>(`/tools/download/config-bulk/${packageId}`, { responseType: 'blob' }),
  portForwardRules: (configId: string) =>
    request<PortForwardRuleRead[]>(`/tools/port-forwards/configs/${configId}`),
  createPortForwardRule: (configId: string, payload: {
    from_node_id: string
    from_port: number
    to_node_id: string
    to_port: number
    to_platform: 'linux' | 'darwin'
    protocol: 'tcp' | 'udp' | 'all'
  }) =>
    request<PortForwardRuleRead>(`/tools/port-forwards/configs/${configId}`, { method: 'POST', data: payload }),
  deletePortForwardRule: (ruleId: string) =>
    request<{ message: string }>(`/tools/port-forwards/${ruleId}`, { method: 'DELETE' }),
  updatePortForwardRuleEnabled: (ruleId: string, enabled: boolean) =>
    request<PortForwardRuleRead>(`/tools/port-forwards/${ruleId}/enabled`, { method: 'PUT', data: { enabled } }),
  mcpTokens: () => request<McpTokenRead[]>('/mcp-access/tokens'),
  createMcpToken: (payload: { name: string; permission: 'read' | 'write'; expires_at: string }) =>
    request<McpTokenRead>('/mcp-access/tokens', { method: 'POST', data: payload }),
  revokeMcpToken: (tokenId: string) =>
    request<McpTokenRead>(`/mcp-access/tokens/${tokenId}/revoke`, { method: 'POST' }),
  mcpAudit: (query: McpAuditQuery = {}) =>
    request<McpAuditRead[]>(`/mcp-access/audit${toQueryString(query)}`),
  clearMcpAudit: (payload: { created_from: string; created_to: string }) =>
    request<McpAuditDeleteResult>('/mcp-access/audit', { method: 'DELETE', data: payload }),
  saveAppliedConf: (configId: string, nodeId: string, content: string) =>
    request<SyncStatusRead>(`/configs/${configId}/nodes/${nodeId}/applied-conf`, {
      method: 'PUT',
      data: { content },
    }),
  syncNode: (configId: string, nodeId: string) =>
    request<{ message: string }>(`/configs/${configId}/nodes/${nodeId}/sync`, { method: 'POST' }),
  syncAll: (configId: string) =>
    request<{ message: string; synced_count: number }>(`/configs/${configId}/sync-all`, {
      method: 'POST',
    }),

  runtimeSnapshot: (configId: string) =>
    request<RuntimeSnapshotItem[]>(`/configs/${configId}/endpoint/runtime-snapshot`),
  endpointStatus: (configId: string, nodeId: string) =>
    request<EndpointStatusRead>(`/configs/${configId}/nodes/${nodeId}/endpoint/status`),
  endpointLogs: (configId: string, nodeId: string) =>
    request<ControlLogRead[]>(`/configs/${configId}/nodes/${nodeId}/endpoint/logs`),
  createClientBindCommand: (configId: string, nodeId: string) =>
    request<ClientBindCommandRead>(`/configs/${configId}/nodes/${nodeId}/bind-command`, {
      method: 'POST',
      data: { server_url: window.location.origin },
    }),
  resetClient: (configId: string, nodeId: string) =>
    request<{ client_state: EndpointStatusRead['client_state'] }>(`/configs/${configId}/nodes/${nodeId}/reset-client`, { method: 'POST' }),
  controlEndpoint: (configId: string, nodeId: string, action: string) =>
    request<{ request_id: string; message: string }>(
      `/configs/${configId}/nodes/${nodeId}/endpoint/control`,
      { method: 'POST', data: { action } },
    ),
  probeBatch: (configId: string, node_ids: string[] = []) =>
    request<{ dispatched: Array<{ node_id: string; request_id: string }> }>(
      `/configs/${configId}/endpoint/probe-batch`,
      { method: 'POST', data: { node_ids } },
    ),

  mqttSettings: () => request<MqttSettingsRead>('/settings/mqtt'),
  uiSettings: () => request<UiSettingsRead>('/settings/ui'),
  updateUiSettings: (payload: UiSettingsRead) =>
    request<UiSettingsRead>('/settings/ui', { method: 'PUT', data: payload }),
  updateMqttSettings: (payload: MqttSettingsRead) =>
    request<MqttSettingsRead>('/settings/mqtt', { method: 'PUT', data: payload }),
  resetMqttSettings: () =>
    request<MqttSettingsRead>('/settings/mqtt/reset', { method: 'POST' }),
  testMqttSettings: (payload: MqttSettingsRead) =>
    request<{ success: boolean; message: string; latency_ms: number }>('/settings/mqtt/test', {
      method: 'POST',
      data: payload,
    }),

  createSnapshot: (note: string, password: string) =>
    request<SnapshotRead>('/backups/snapshot', { method: 'POST', data: { note, password } }),
  snapshots: () => request<SnapshotRead[]>('/backups/list'),
  exportSnapshot: (snapshotId: string) =>
    request<Blob>(`/backups/export/${snapshotId}`, { responseType: 'blob' }),
  importSnapshot: (file: File) => {
    const data = new FormData()
    data.append('file', file)
    return request<SnapshotRead>('/backups/import', { method: 'POST', data })
  },
  restoreSnapshot: (snapshotId: string, password: string) =>
    request<{ message: string }>(`/backups/restore/${snapshotId}`, { method: 'POST', data: { password } }),
  deleteSnapshot: (snapshotId: string) =>
    request<{ message: string }>(`/backups/${snapshotId}`, { method: 'DELETE' }),
  updateSnapshotNote: (snapshotId: string, note: string) =>
    request<SnapshotRead>(`/backups/${snapshotId}/note`, { method: 'PUT', data: note }),
}
