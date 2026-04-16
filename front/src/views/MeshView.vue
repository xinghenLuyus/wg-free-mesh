<script setup lang="ts">
import { EditPen, Key, Plus } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type {
  MeshWorkspaceUpdatedPayload,
  MeshConnectionDirectionRead,
  MeshConnectionRead,
  MeshWorkspaceRead,
  NodeRead,
  PeerLinkDraftRead,
  RealtimeEvent,
} from '@/types/api'
import { notify } from '@/utils/notify'

const route = useRoute()

type EndpointMode = 'auto' | 'none' | 'manual'
type EndpointFamily = 'ipv4' | 'ipv6'
type DialogMode = 'create' | 'edit'

const workspace = shallowRef<MeshWorkspaceRead | null>(null)
const nodes = shallowRef<NodeRead[]>([])
const draft = shallowRef<PeerLinkDraftRead | null>(null)
const draftLoading = shallowRef(false)
const draftRequestToken = shallowRef(0)
const dialogVisible = shallowRef(false)
const dialogMode = shallowRef<DialogMode>('create')
const editingConnection = shallowRef<MeshConnectionRead | null>(null)

const form = reactive({
  local_node_id: '',
  peer_node_id: '',
  endpoint_ref_family: 'ipv4' as EndpointFamily,
  forward_allowed_ips: '',
  forward_persistent_keepalive: 25 as number | null,
  forward_endpoint_mode: 'auto' as EndpointMode,
  forward_manual_host: '',
  forward_manual_port: null as number | null,
  reverse_allowed_ips: '',
  reverse_persistent_keepalive: null as number | null,
  reverse_endpoint_mode: 'auto' as EndpointMode,
  reverse_manual_host: '',
  reverse_manual_port: null as number | null,
  preshared_key: '',
  notes: '',
  enabled: true,
})

const currentNodeId = computed(() => String(route.params.nodeId))
const currentNode = computed(() => workspace.value?.node ?? nodes.value.find((item) => item.id === currentNodeId.value) ?? null)
const connections = computed(() => workspace.value?.connections ?? [])
const validation = computed(() => workspace.value?.validation ?? null)
const peerOptions = computed(() => nodes.value.filter((item) => item.id !== currentNodeId.value))
const selectedPeer = computed(() => nodes.value.find((item) => item.id === form.peer_node_id) ?? editingConnection.value?.peer_node ?? null)
const draftWarnings = computed(() => draft.value?.warnings ?? [])
const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建连接' : '修改连接参数'))
const submitText = computed(() => (dialogMode.value === 'create' ? '创建' : '保存'))
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'mesh.workspace.updated') return
  const payload = event.payload as unknown as MeshWorkspaceUpdatedPayload
  if (payload.config_id !== String(route.params.configId) || payload.node_id !== currentNodeId.value) return
  workspace.value = payload.workspace
  nodes.value = payload.nodes
})

const endpointModeLabel: Record<EndpointMode, string> = {
  auto: '自动',
  none: '不写 Endpoint',
  manual: '手动',
}

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? '静态节点' : '动态节点'
}

function directionTitle(direction: MeshConnectionDirectionRead | null, fallback: string) {
  if (!direction) return fallback
  const local = direction.local_node_id === currentNodeId.value ? currentNode.value : selectedPeer.value
  const peer = direction.peer_node_id === currentNodeId.value ? currentNode.value : selectedPeer.value
  return `${local?.name || '本端'} -> ${peer?.name || '对端'}`
}

function endpointSummary(summary: string | undefined, mode: EndpointMode, host: string, port: number | null) {
  if (mode === 'none') return '不写 Endpoint'
  if (mode === 'manual') return host && port ? '手动模式将使用填写的 Host 和 Port' : '手动模式需填写 Host 和 Port'
  return summary || '正在读取后端连接草稿'
}

const forwardEndpointSummaryText = computed(() => {
  const summary =
    dialogMode.value === 'edit'
      ? editingConnection.value?.forward.endpoint_summary
      : draft.value?.forward.endpoint_summary
  return endpointSummary(summary, form.forward_endpoint_mode, form.forward_manual_host, form.forward_manual_port)
})

const reverseEndpointSummaryText = computed(() => {
  const summary =
    dialogMode.value === 'edit'
      ? editingConnection.value?.reverse?.endpoint_summary
      : draft.value?.reverse.endpoint_summary
  return endpointSummary(summary, form.reverse_endpoint_mode, form.reverse_manual_host, form.reverse_manual_port)
})

function connectionEndpointFamily(connection: MeshConnectionRead) {
  return connection.forward.endpoint_ref_family || connection.reverse?.endpoint_ref_family || 'ipv4'
}

function applyDirection(prefix: 'forward' | 'reverse', direction: MeshConnectionDirectionRead) {
  form[`${prefix}_allowed_ips`] = direction.allowed_ips
  form[`${prefix}_persistent_keepalive`] = direction.persistent_keepalive
  form[`${prefix}_endpoint_mode`] = direction.endpoint_mode
  form[`${prefix}_manual_host`] = direction.endpoint_manual_host || ''
  form[`${prefix}_manual_port`] = direction.endpoint_manual_port
}

function applyDraft(nextDraft: PeerLinkDraftRead) {
  form.local_node_id = currentNodeId.value
  form.endpoint_ref_family = nextDraft.endpoint_ref_family
  form.forward_allowed_ips = nextDraft.forward.allowed_ips
  form.reverse_allowed_ips = nextDraft.reverse.allowed_ips
  form.forward_persistent_keepalive = nextDraft.forward.persistent_keepalive
  form.reverse_persistent_keepalive = nextDraft.reverse.persistent_keepalive
  form.forward_endpoint_mode = nextDraft.forward.endpoint_mode
  form.reverse_endpoint_mode = nextDraft.reverse.endpoint_mode
  form.forward_manual_host = nextDraft.forward.endpoint_manual_host
  form.forward_manual_port = nextDraft.forward.endpoint_manual_port
  form.reverse_manual_host = nextDraft.reverse.endpoint_manual_host
  form.reverse_manual_port = nextDraft.reverse.endpoint_manual_port
  form.preshared_key = ''
  form.notes = ''
  form.enabled = true
}

async function loadDraft() {
  if (!dialogVisible.value || dialogMode.value !== 'create' || !form.peer_node_id) return
  const requestToken = draftRequestToken.value + 1
  draftRequestToken.value = requestToken
  draftLoading.value = true
  try {
    const nextDraft = await api.peerLinkDraft(
      String(route.params.configId),
      currentNodeId.value,
      form.peer_node_id,
      form.endpoint_ref_family,
    )
    if (
      requestToken !== draftRequestToken.value ||
      !dialogVisible.value ||
      dialogMode.value !== 'create' ||
      form.peer_node_id !== nextDraft.peer_node.id
    ) {
      return
    }
    draft.value = nextDraft
    applyDraft(nextDraft)
  } catch (error) {
    if (requestToken === draftRequestToken.value && dialogVisible.value && dialogMode.value === 'create') {
      notify.error(error instanceof ApiClientError ? error.message : '连接草稿生成失败')
    }
  } finally {
    if (requestToken === draftRequestToken.value) {
      draftLoading.value = false
    }
  }
}

async function load() {
  const configId = String(route.params.configId)
  const [nextWorkspace, nextNodes] = await Promise.all([
    api.meshWorkspace(configId, currentNodeId.value),
    api.nodes(configId),
  ])
  workspace.value = nextWorkspace
  nodes.value = nextNodes
  form.local_node_id = currentNodeId.value
}

async function openCreate() {
  dialogMode.value = 'create'
  editingConnection.value = null
  draftRequestToken.value += 1
  draftLoading.value = false
  form.local_node_id = currentNodeId.value
  form.peer_node_id = peerOptions.value[0]?.id || ''
  form.endpoint_ref_family = 'ipv4'
  draft.value = null
  dialogVisible.value = true
  await loadDraft()
}

function openEdit(connection: MeshConnectionRead) {
  dialogMode.value = 'edit'
  editingConnection.value = connection
  draftRequestToken.value += 1
  draft.value = null
  draftLoading.value = false
  form.local_node_id = currentNodeId.value
  form.peer_node_id = connection.peer_node.id
  form.endpoint_ref_family = connectionEndpointFamily(connection)
  form.preshared_key = connection.preshared_key || ''
  form.notes = connection.notes
  form.enabled = connection.enabled
  applyDirection('forward', connection.forward)
  if (connection.reverse) {
    applyDirection('reverse', connection.reverse)
  }
  dialogVisible.value = true
}

async function generatePsk() {
  try {
    const result = await api.generatePresharedKey()
    form.preshared_key = result.preshared_key
    notify.success('PSK 已生成')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : 'PSK 生成失败')
  }
}

function buildPayload() {
  return {
    enabled: form.enabled,
    notes: form.notes,
    preshared_key: form.preshared_key || null,
    forward: {
      local_node_id: currentNodeId.value,
      peer_node_id: form.peer_node_id,
      allowed_ips: form.forward_allowed_ips,
      persistent_keepalive: form.forward_persistent_keepalive,
      endpoint_mode: form.forward_endpoint_mode,
      endpoint_ref_family: form.forward_endpoint_mode === 'auto' ? form.endpoint_ref_family : null,
      endpoint_manual_host: form.forward_endpoint_mode === 'manual' ? form.forward_manual_host : null,
      endpoint_port_mode: form.forward_endpoint_mode === 'manual' ? 'manual' : 'ref_peer_listen_port',
      endpoint_manual_port: form.forward_endpoint_mode === 'manual' ? form.forward_manual_port : null,
    },
    reverse: {
      local_node_id: form.peer_node_id,
      peer_node_id: currentNodeId.value,
      allowed_ips: form.reverse_allowed_ips,
      persistent_keepalive: form.reverse_persistent_keepalive,
      endpoint_mode: form.reverse_endpoint_mode,
      endpoint_ref_family: form.reverse_endpoint_mode === 'auto' ? form.endpoint_ref_family : null,
      endpoint_manual_host: form.reverse_endpoint_mode === 'manual' ? form.reverse_manual_host : null,
      endpoint_port_mode: form.reverse_endpoint_mode === 'manual' ? 'manual' : 'ref_peer_listen_port',
      endpoint_manual_port: form.reverse_endpoint_mode === 'manual' ? form.reverse_manual_port : null,
    },
  }
}

function directionPayload(direction: MeshConnectionDirectionRead) {
  return {
    local_node_id: direction.local_node_id,
    peer_node_id: direction.peer_node_id,
    allowed_ips: direction.allowed_ips,
    persistent_keepalive: direction.persistent_keepalive,
    endpoint_mode: direction.endpoint_mode,
    endpoint_ref_family: direction.endpoint_mode === 'auto' ? direction.endpoint_ref_family : null,
    endpoint_manual_host: direction.endpoint_mode === 'manual' ? direction.endpoint_manual_host : null,
    endpoint_port_mode: direction.endpoint_mode === 'manual' ? direction.endpoint_port_mode : 'ref_peer_listen_port',
    endpoint_manual_port: direction.endpoint_mode === 'manual' ? direction.endpoint_manual_port : null,
  }
}

async function toggleConnection(connection: MeshConnectionRead, enabled: boolean) {
  if (!connection.reverse) {
    notify.error('缺少反向连接参数，无法直接切换')
    return
  }
  try {
    await api.updatePeerLinkGroup(connection.link_group_id, {
      enabled,
      notes: connection.notes,
      preshared_key: connection.preshared_key || null,
      forward: directionPayload(connection.forward),
      reverse: directionPayload(connection.reverse),
    })
    await load()
    notify.success(enabled ? 'Peer 已启用' : 'Peer 已停用')
  } catch (error) {
    await load()
    notify.error(error instanceof ApiClientError ? error.message : 'Peer 状态保存失败')
  }
}

async function submit() {
  try {
    if (dialogMode.value === 'create') {
      await api.createPeerLink(String(route.params.configId), buildPayload())
      notify.success('连接已创建')
    } else if (editingConnection.value) {
      await api.updatePeerLinkGroup(editingConnection.value.link_group_id, buildPayload())
      notify.success('连接参数已保存')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '连接保存失败')
  }
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    await load()
  },
)

watch(
  () => [form.peer_node_id, form.endpoint_ref_family],
  () => {
    void loadDraft()
  },
)

onMounted(async () => {
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : 'Mesh 页面加载失败')
  }
})
</script>

<template>
  <section class="node-template">
    <div class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>Mesh 网络</h2>
          <p>管理当前节点的 Peer 连接关系。</p>
        </div>
        <div class="template-toolbar__actions">
          <el-button type="primary" :icon="Plus" @click="openCreate">新建连接</el-button>
          <el-tag v-if="validation" :type="validation.valid ? 'success' : 'warning'">
            {{ validation.valid ? '拓扑校验通过' : '拓扑校验有警告' }}
          </el-tag>
        </div>
      </div>

      <div v-if="connections.length" class="connection-list">
        <article
          v-for="connection in connections"
          :key="connection.link_group_id"
          class="mesh-card"
          :class="{ 'mesh-card--disabled': !connection.enabled }"
        >
          <section class="mesh-direction">
            <div class="mesh-direction__head">
              <div class="mesh-direction__identity">
                <div class="mesh-direction__title-row">
                <div class="mesh-direction__title">{{ directionTitle(connection.forward, '本端到对端') }}</div>
                  <el-tag :type="connection.has_preshared_key ? 'success' : 'info'" size="small">
                    {{ connection.has_preshared_key ? 'PSK 已配置' : '未配置 PSK' }}
                  </el-tag>
                </div>
              </div>
              <div class="mesh-direction__actions">
                <div class="peer-switch">
                  <span>{{ connection.enabled ? '启用' : '停用' }}</span>
                  <el-switch
                    size="small"
                    :model-value="connection.enabled"
                    @change="(value: boolean | string | number) => toggleConnection(connection, Boolean(value))"
                  />
                </div>
                <el-button :icon="EditPen" plain size="small" @click="openEdit(connection)">修改参数</el-button>
              </div>
            </div>
            <dl>
              <div>
                <dt>AllowedIPs</dt>
                <dd>{{ connection.forward.allowed_ips }}</dd>
              </div>
              <div>
                <dt>Endpoint</dt>
                <dd>{{ endpointModeLabel[connection.forward.endpoint_mode] }} · {{ connection.forward.endpoint_summary }}</dd>
              </div>
              <div>
                <dt>Keepalive</dt>
                <dd>{{ connection.forward.persistent_keepalive ?? '未设置' }}</dd>
              </div>
              <div>
                <dt>地址族</dt>
                <dd>{{ connection.forward.endpoint_ref_family?.toUpperCase() || '无' }}</dd>
              </div>
            </dl>
          </section>
        </article>
      </div>
      <div v-else class="empty-state">当前节点还没有连接。</div>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Plus /></el-icon></span>
        <div>
          <h3>{{ dialogMode === 'create' ? '建立 Peer 连接' : '调整 Peer 参数' }}</h3>
          <p>连接关系只作用于当前节点和选定对端。</p>
        </div>
      </div>
      <el-form v-loading="draftLoading" class="dialog-form" label-position="top">
        <el-form-item label="本地节点">
          <el-input :model-value="currentNode?.name || currentNodeId" disabled />
        </el-form-item>
        <el-form-item label="对端节点">
          <el-select v-if="dialogMode === 'create'" v-model="form.peer_node_id" style="width: 100%">
            <el-option
              v-for="node in peerOptions"
              :key="node.id"
              :value="node.id"
              :label="`${node.name} · ${nodeTypeLabel(node.node_type)} · IPv4 ${node.ipv4_address || '未设置'} · IPv6 ${node.ipv6_address || '未设置'}`"
            />
          </el-select>
          <el-input v-else :model-value="selectedPeer?.name || form.peer_node_id" disabled />
        </el-form-item>
        <el-form-item label="连接地址族">
          <el-segmented
            v-model="form.endpoint_ref_family"
            :options="[
              { label: 'IPv4', value: 'ipv4' },
              { label: 'IPv6', value: 'ipv6' },
            ]"
          />
          <p class="field-hint">自动模式会读取对向节点对应的公网入口；没有对应入口时不写 Endpoint。</p>
        </el-form-item>
        <div v-if="draftWarnings.length" class="draft-warnings">
          <span v-for="item in draftWarnings" :key="item">{{ item }}</span>
        </div>

        <section class="connection-panel">
          <div class="connection-panel__head">
            <strong>主向配置</strong>
            <span>{{ currentNode?.name || '当前节点' }} -> {{ selectedPeer?.name || '对端节点' }}</span>
          </div>
          <el-form-item label="主向 AllowedIPs">
            <el-input v-model="form.forward_allowed_ips" placeholder="默认使用对端虚拟 IP" />
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="主向 Keepalive">
              <el-input-number v-model="form.forward_persistent_keepalive" :min="0" :max="65535" style="width: 100%" />
            </el-form-item>
            <el-form-item label="主向 Endpoint">
              <el-select v-model="form.forward_endpoint_mode" style="width: 100%">
                <el-option label="自动" value="auto" />
                <el-option label="不写 Endpoint" value="none" />
                <el-option label="手动（不推荐）" value="manual" />
              </el-select>
            </el-form-item>
          </div>
          <p class="endpoint-summary">
            {{ forwardEndpointSummaryText }}
          </p>
          <div v-if="form.forward_endpoint_mode === 'manual'" class="form-grid">
            <el-form-item label="主向手动 Host">
              <el-input v-model="form.forward_manual_host" placeholder="IP 或域名" />
            </el-form-item>
            <el-form-item label="主向手动 Port">
              <el-input-number v-model="form.forward_manual_port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </div>
        </section>

        <section class="connection-panel">
          <div class="connection-panel__head">
            <strong>反向配置</strong>
            <span>{{ selectedPeer?.name || '对端节点' }} -> {{ currentNode?.name || '当前节点' }}</span>
          </div>
          <el-form-item label="反向 AllowedIPs">
            <el-input v-model="form.reverse_allowed_ips" placeholder="默认使用当前节点虚拟 IP" />
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="反向 Keepalive">
              <el-input-number v-model="form.reverse_persistent_keepalive" :min="0" :max="65535" style="width: 100%" />
            </el-form-item>
            <el-form-item label="反向 Endpoint">
              <el-select v-model="form.reverse_endpoint_mode" style="width: 100%">
                <el-option label="自动" value="auto" />
                <el-option label="不写 Endpoint" value="none" />
                <el-option label="手动（不推荐）" value="manual" />
              </el-select>
            </el-form-item>
          </div>
          <p class="endpoint-summary">
            {{ reverseEndpointSummaryText }}
          </p>
          <div v-if="form.reverse_endpoint_mode === 'manual'" class="form-grid">
            <el-form-item label="反向手动 Host">
              <el-input v-model="form.reverse_manual_host" placeholder="IP 或域名" />
            </el-form-item>
            <el-form-item label="反向手动 Port">
              <el-input-number v-model="form.reverse_manual_port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </div>
        </section>

        <section class="connection-panel">
          <div class="connection-panel__head">
            <strong>安全与备注</strong>
            <span>PSK 可为空，也可以自动生成。</span>
          </div>
          <el-form-item label="共享密钥 PSK">
            <el-input v-model="form.preshared_key" placeholder="可为空">
              <template #append>
                <el-button :icon="Key" @click="generatePsk">自动生成</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" /></el-form-item>
          <div class="switch-row">
            <div>
              <strong>启用连接</strong>
              <span>停用后保留参数，但不会参与生成配置。</span>
            </div>
            <el-switch v-model="form.enabled" />
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">{{ submitText }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.node-template { display: grid; gap: 20px; }
.template-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.template-toolbar h2 { margin: 0; color: var(--app-text); font-size: 22px; }
.template-toolbar p { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.template-toolbar__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.connection-list { display: grid; gap: 8px; }
.mesh-card { min-width: 0; }
.mesh-card--disabled .mesh-direction {
  background: #f3f6f5;
  box-shadow: none;
}
.mesh-card--disabled .mesh-direction__title,
.mesh-card--disabled .mesh-direction dd,
.mesh-card--disabled .peer-switch {
  color: #8a9a94;
}
.mesh-card--disabled .mesh-direction dt,
.mesh-card--disabled .mesh-direction__actions {
  opacity: 0.72;
}
.peer-switch { display: inline-flex; align-items: center; gap: 7px; min-height: 30px; padding: 4px 8px; border: 1px solid #dce7e3; border-radius: 8px; background: #f8fbf9; color: #4b6259; font-size: 12px; font-weight: 750; }
.mesh-direction { padding: 10px 12px; border: 1px solid #d8e1dd; border-radius: 8px; background: #ffffff; box-shadow: var(--app-shadow-sm); }
.mesh-direction__head { display: grid; grid-template-columns: minmax(180px, 1fr) auto; align-items: center; gap: 10px; }
.mesh-direction__identity { min-width: 0; }
.mesh-direction__title-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.mesh-direction__title { color: #21302a; font-size: 17px; font-weight: 850; line-height: 1.25; }
.mesh-direction__actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.mesh-direction dl { display: grid; grid-template-columns: minmax(150px, 1fr) minmax(220px, 1.5fr) minmax(80px, 0.6fr) minmax(70px, 0.5fr); gap: 10px; margin: 10px 0 0; }
.mesh-direction dt { color: #73877f; font-size: 12px; font-weight: 650; }
.mesh-direction dd { margin: 4px 0 0; overflow: hidden; color: #21302a; font-size: 13px; font-weight: 700; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { display: grid; place-items: center; min-height: 170px; border: 1px dashed var(--app-border-strong); border-radius: 8px; background: rgba(255, 255, 255, 0.72); color: var(--app-muted); }
.dialog-intro { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; padding: 14px; border: 1px solid #e1ebe7; border-radius: 8px; background: #f8fbf9; }
.dialog-intro__icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 42px; height: 42px; border: 1px solid #bfe0da; border-radius: 8px; background: var(--app-primary-soft); color: var(--app-primary); }
.dialog-intro h3 { margin: 0; color: var(--app-text); }
.dialog-intro p { margin: 5px 0 0; color: var(--app-muted); line-height: 1.5; }
.dialog-form { display: grid; gap: 2px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.field-hint { margin: 8px 0 0; color: var(--app-muted); font-size: 13px; line-height: 1.5; }
.draft-warnings { display: grid; gap: 6px; margin: 0 0 10px; padding: 10px 12px; border: 1px solid #f0d9a6; border-radius: 8px; background: #fffaf0; color: #8a5a13; font-size: 13px; line-height: 1.5; }
.connection-panel { display: grid; gap: 2px; margin: 8px 0 12px; padding: 14px; border: 1px solid #e1ebe7; border-radius: 8px; background: #fbfdfc; }
.connection-panel__head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; color: var(--app-text); }
.connection-panel__head span { color: var(--app-muted); font-size: 13px; }
.endpoint-summary { margin: -2px 0 12px; padding: 9px 10px; border-radius: 8px; background: #f3f8f6; color: #4a625a; font-size: 13px; line-height: 1.5; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px; border: 1px solid #e1ebe7; border-radius: 8px; background: #fff; }
.switch-row strong, .switch-row span { display: block; }
.switch-row strong { color: var(--app-text); }
.switch-row span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
@media (max-width: 980px) {
  .mesh-direction dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } .mesh-direction__head { grid-template-columns: 1fr; } .mesh-direction__actions { justify-content: flex-start; } }
@media (max-width: 720px) { .form-grid, .mesh-direction dl { grid-template-columns: 1fr; } }
</style>
