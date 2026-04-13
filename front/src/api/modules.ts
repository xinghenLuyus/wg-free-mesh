import { request } from '@/api/client'
import type {
  ConfigOverviewRead,
  ConfigRead,
  ControlLogRead,
  EndpointStatusRead,
  HealthRead,
  MeshValidationRead,
  MqttSettingsRead,
  NodeRead,
  PeerLinkRead,
  SessionRead,
  SnapshotRead,
  SyncStatusRead,
  SystemStatusRead,
  RuntimeSnapshotItem,
  WgPreviewRead,
} from '@/types/api'

export const api = {
  login: (username: string, password: string) =>
    request<SessionRead>('/auth/login', { method: 'POST', data: { username, password } }),
  session: () => request<SessionRead>('/auth/session'),
  logout: () => request<SessionRead>('/auth/logout', { method: 'POST' }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ message: string }>('/auth/password', {
      method: 'POST',
      data: { current_password, new_password },
    }),

  health: () => request<HealthRead>('/system/health'),
  systemStatus: () => request<SystemStatusRead>('/system/status'),

  configs: () => request<ConfigRead[]>('/configs'),
  configOverview: (configId: string) => request<ConfigOverviewRead>(`/configs/${configId}/overview`),
  createConfig: (payload: Record<string, unknown>) =>
    request<ConfigRead>('/configs', { method: 'POST', data: payload }),
  updateConfig: (configId: string, payload: Record<string, unknown>) =>
    request<ConfigRead>(`/configs/${configId}`, { method: 'PUT', data: payload }),
  deleteConfig: (configId: string) =>
    request<{ message: string }>(`/configs/${configId}`, { method: 'DELETE' }),

  nodes: (configId: string) => request<NodeRead[]>(`/configs/${configId}/nodes`),
  node: (nodeId: string) => request<NodeRead>(`/nodes/${nodeId}`),
  createNode: (configId: string, payload: Record<string, unknown>) =>
    request<NodeRead>(`/configs/${configId}/nodes`, { method: 'POST', data: payload }),
  updateNode: (nodeId: string, payload: Record<string, unknown>) =>
    request<NodeRead>(`/nodes/${nodeId}`, { method: 'PUT', data: payload }),
  deleteNode: (nodeId: string) =>
    request<{ message: string }>(`/nodes/${nodeId}`, { method: 'DELETE' }),
  suggestIp: (configId: string) =>
    request<{ ip: string }>(`/configs/${configId}/nodes/suggest-ip`, { method: 'POST' }),
  validateIp: (configId: string, virtual_ip: string) =>
    request<{ valid: boolean; warning: string }>(`/configs/${configId}/nodes/validate-ip`, {
      method: 'POST',
      data: { virtual_ip },
    }),
  generateKeys: () => request<{ private_key: string; public_key: string }>('/nodes/keys/generate', { method: 'POST' }),

  peerLinks: (configId: string) => request<PeerLinkRead[]>(`/configs/${configId}/peer-links`),
  createPeerLink: (configId: string, payload: Record<string, unknown>) =>
    request<PeerLinkRead[]>(`/configs/${configId}/peer-links`, { method: 'POST', data: payload }),
  updatePeerLinkGroup: (groupId: string, payload: Record<string, unknown>) =>
    request<PeerLinkRead[]>(`/peer-links/${groupId}`, { method: 'PUT', data: payload }),
  deletePeerLinkGroup: (groupId: string) =>
    request<{ message: string }>(`/peer-links/${groupId}`, { method: 'DELETE' }),
  validateMesh: (configId: string) =>
    request<MeshValidationRead>(`/configs/${configId}/mesh/validate`, { method: 'POST' }),
  wgPreview: (configId: string, nodeId: string) =>
    request<WgPreviewRead>(`/configs/${configId}/nodes/${nodeId}/wg-preview`),

  syncStatuses: (configId: string) => request<SyncStatusRead[]>(`/configs/${configId}/sync-status`),
  nodeSyncStatus: (configId: string, nodeId: string) =>
    request<SyncStatusRead>(`/configs/${configId}/nodes/${nodeId}/sync-status`),
  readAppliedConf: (configId: string, nodeId: string) =>
    request<{ content: string; exists: boolean; node_name: string; node_type: string; desired_version: number; staged_version: number }>(
      `/configs/${configId}/nodes/${nodeId}/applied-conf`,
    ),
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
  updateMqttSettings: (payload: MqttSettingsRead) =>
    request<MqttSettingsRead>('/settings/mqtt', { method: 'PUT', data: payload }),
  testMqttSettings: (payload: MqttSettingsRead) =>
    request<{ success: boolean; message: string; latency_ms: number }>('/settings/mqtt/test', {
      method: 'POST',
      data: payload,
    }),

  createSnapshot: (note: string) =>
    request<SnapshotRead>('/backups/snapshot', { method: 'POST', data: note }),
  snapshots: () => request<SnapshotRead[]>('/backups/list'),
  restoreSnapshot: (snapshotId: string) =>
    request<{ message: string }>(`/backups/restore/${snapshotId}`, { method: 'POST' }),
  deleteSnapshot: (snapshotId: string) =>
    request<{ message: string }>(`/backups/${snapshotId}`, { method: 'DELETE' }),
  updateSnapshotNote: (snapshotId: string, note: string) =>
    request<SnapshotRead>(`/backups/${snapshotId}/note`, { method: 'PUT', data: note }),
}
