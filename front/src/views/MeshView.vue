<script setup lang="ts">
import { Delete, EditPen, Key, Plus } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
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
import { requiredSelectionRule, requiredTextRule } from '@/utils/formRules'
import { translateMeshText } from '@/utils/meshText'
import { notify } from '@/utils/notify'

const route = useRoute()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const creatingConnection = actions.isPending('submit-connection')
const generatingPsk = actions.isPending('generate-psk')
const deletingConnection = actions.isPending('delete-connection')

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
const formRef = shallowRef<FormInstance>()

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
const readonlyMesh = computed(() => workspace.value?.readonly === true || currentNode.value?.enabled === false)
const peerOptions = computed(() => nodes.value.filter((item) => item.id !== currentNodeId.value && item.enabled))
const selectedPeer = computed(() => nodes.value.find((item) => item.id === form.peer_node_id) ?? editingConnection.value?.peer_node ?? null)
const draftWarnings = computed(() => draft.value?.warnings ?? [])
const dialogTitle = computed(() => (dialogMode.value === 'create' ? t('mesh.newConnection') : t('mesh.editConnection')))
const submitText = computed(() => (dialogMode.value === 'create' ? t('mesh.create') : t('common.save')))
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'mesh.workspace.updated') return
  const payload = event.payload as unknown as MeshWorkspaceUpdatedPayload
  if (payload.config_id !== String(route.params.configId) || payload.node_id !== currentNodeId.value) return
  workspace.value = payload.workspace
  nodes.value = payload.nodes
})
const formRules: FormRules<typeof form> = {
  peer_node_id: [requiredSelectionRule('mesh.peerNode')],
  forward_allowed_ips: [requiredTextRule('mesh.forwardAllowedIps')],
  reverse_allowed_ips: [requiredTextRule('mesh.reverseAllowedIps')],
  forward_manual_host: [
    {
      trigger: ['blur', 'change'],
      validator: (_rule, value, callback) => {
        if (form.forward_endpoint_mode === 'manual' && !String(value || '').trim()) {
          callback(new Error(t('validation.required', { field: t('mesh.forwardManualHost') })))
          return
        }
        callback()
      },
    },
  ],
  reverse_manual_host: [
    {
      trigger: ['blur', 'change'],
      validator: (_rule, value, callback) => {
        if (form.reverse_endpoint_mode === 'manual' && !String(value || '').trim()) {
          callback(new Error(t('validation.required', { field: t('mesh.reverseManualHost') })))
          return
        }
        callback()
      },
    },
  ],
  forward_manual_port: [
    {
      trigger: ['blur', 'change'],
      validator: (_rule, value, callback) => {
        if (form.forward_endpoint_mode === 'manual' && !value) {
          callback(new Error(t('validation.required', { field: t('mesh.forwardManualPort') })))
          return
        }
        callback()
      },
    },
  ],
  reverse_manual_port: [
    {
      trigger: ['blur', 'change'],
      validator: (_rule, value, callback) => {
        if (form.reverse_endpoint_mode === 'manual' && !value) {
          callback(new Error(t('validation.required', { field: t('mesh.reverseManualPort') })))
          return
        }
        callback()
      },
    },
  ],
}

const endpointModeLabel = computed<Record<EndpointMode, string>>(() => ({
  auto: t('mesh.auto'),
  none: t('mesh.noneEndpoint'),
  manual: t('mesh.manual'),
}))

function connectionToggleKey(linkGroupId: string) {
  return `toggle-connection:${linkGroupId}`
}

function connectionToggleLoading(linkGroupId: string) {
  return actions.hasPending(connectionToggleKey(linkGroupId))
}

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? t('nodeWorkspace.staticNode') : t('nodeWorkspace.dynamicNode')
}

function nodeNameById(nodeId: string | null | undefined) {
  if (!nodeId) return t('mesh.peerNode')
  if (nodeId === currentNodeId.value) return currentNode.value?.name || t('mesh.currentNode')
  return nodes.value.find((item) => item.id === nodeId)?.name || nodeId
}

function directionTitle(direction: MeshConnectionDirectionRead | null, fallback: string) {
  if (!direction) return fallback
  return `${nodeNameById(direction.local_node_id)} -> ${nodeNameById(direction.peer_node_id)}`
}

function endpointSummary(summary: string | undefined, mode: EndpointMode, host: string, port: number | null) {
  if (mode === 'none') return t('mesh.noneEndpoint')
  if (mode === 'manual') return host && port ? t('mesh.manualUseHostPort') : t('mesh.manualNeedHostPort')
  return summary ? translateMeshText(summary, t) : t('mesh.readingDraft')
}

function meshText(value: string | undefined) {
  return translateMeshText(String(value || ''), t)
}

const forwardEndpointSummaryText = computed(() => {
  const summary = draft.value?.forward.endpoint_summary ?? (
    dialogMode.value === 'edit' ? editingConnection.value?.forward.endpoint_summary : undefined
  )
  return endpointSummary(summary, form.forward_endpoint_mode, form.forward_manual_host, form.forward_manual_port)
})

const reverseEndpointSummaryText = computed(() => {
  const summary = draft.value?.reverse.endpoint_summary ?? (
    dialogMode.value === 'edit' ? editingConnection.value?.reverse?.endpoint_summary : undefined
  )
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
  if (!dialogVisible.value || !form.peer_node_id) return
  const requestToken = draftRequestToken.value + 1
  draftRequestToken.value = requestToken
  draftLoading.value = true
  draft.value = null
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
      form.peer_node_id !== nextDraft.peer_node.id
    ) {
      return
    }
    draft.value = nextDraft
    if (dialogMode.value === 'create') {
      applyDraft(nextDraft)
    }
  } catch (error) {
    if (requestToken === draftRequestToken.value && dialogVisible.value) {
      notify.error(error instanceof ApiClientError ? error.message : t('mesh.draftFailed'))
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
  if (readonlyMesh.value) {
    notify.info(t('mesh.disabledNodeReadonly'))
    return
  }
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
  if (readonlyMesh.value || connection.readonly) {
    notify.info(t('mesh.disabledNodeReadonly'))
    return
  }
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
  void loadDraft()
}

async function generatePsk() {
  await actions.run('generate-psk', async () => {
    try {
      const result = await api.generatePresharedKey()
      form.preshared_key = result.preshared_key
      notify.success(t('mesh.pskGenerated'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('mesh.pskFailed'))
    }
  })
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
  if (readonlyMesh.value || connection.readonly) {
    notify.info(t('mesh.disabledNodeReadonly'))
    return
  }
  const reverse = connection.reverse
  if (!reverse) {
    notify.error(t('mesh.missingReverse'))
    return
  }
  await actions.run(connectionToggleKey(connection.link_group_id), async () => {
    try {
      await api.updatePeerLinkGroup(connection.link_group_id, {
        enabled,
        notes: connection.notes,
        preshared_key: connection.preshared_key || null,
        forward: directionPayload(connection.forward),
        reverse: directionPayload(reverse),
      })
      await load()
      notify.success(enabled ? t('mesh.peerEnabled') : t('mesh.peerDisabled'))
    } catch (error) {
      await load()
      notify.error(error instanceof ApiClientError ? error.message : t('mesh.peerStateSaveFailed'))
    }
  })
}

async function submit() {
  if (readonlyMesh.value) {
    notify.info(t('mesh.disabledNodeReadonly'))
    return
  }
  await actions.run('submit-connection', async () => {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return
    try {
      if (dialogMode.value === 'create') {
        await api.createPeerLink(String(route.params.configId), buildPayload())
        notify.success(t('mesh.created'))
      } else if (editingConnection.value) {
        await api.updatePeerLinkGroup(editingConnection.value.link_group_id, buildPayload())
        notify.success(t('mesh.saved'))
      }
      dialogVisible.value = false
      await load()
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('mesh.saveFailed'))
    }
  })
}

async function deleteConnection() {
  if (readonlyMesh.value) {
    notify.info(t('mesh.disabledNodeReadonly'))
    return
  }
  if (!editingConnection.value) return
  try {
    await ElMessageBox.confirm(
      t('mesh.deleteConnectionConfirm'),
      t('mesh.deleteConnectionTitle'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
      },
    )
  } catch {
    return
  }

  await actions.run('delete-connection', async () => {
    try {
      await api.deletePeerLinkGroup(editingConnection.value!.link_group_id)
      dialogVisible.value = false
      editingConnection.value = null
      await load()
      notify.success(t('mesh.deleted'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('mesh.deleteFailed'))
    }
  })
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
    notify.error(error instanceof ApiClientError ? error.message : t('mesh.loadFailed'))
  }
})
</script>

<template>
  <section class="node-template">
    <div class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>{{ t('mesh.title') }}</h2>
          <p>{{ t('mesh.description') }}</p>
        </div>
        <div class="template-toolbar__actions">
          <el-tag v-if="readonlyMesh" type="info">{{ t('mesh.disabledNodeReadonly') }}</el-tag>
          <el-button type="primary" :icon="Plus" :disabled="readonlyMesh" @click="openCreate">{{ t('mesh.newConnection') }}</el-button>
          <el-tag v-if="validation" :type="validation.valid ? 'success' : 'danger'">
            {{ validation.valid ? t('mesh.topologyOk') : t('mesh.topologyFailed') }}
          </el-tag>
        </div>
      </div>

      <div v-if="connections.length" class="connection-list">
        <article
          v-for="connection in connections"
          :key="connection.link_group_id"
          class="mesh-card"
          :class="{
            'mesh-card--disabled': !connection.enabled,
            'mesh-card--broken': connection.integrity_status === 'broken' || connection.duplicate_enabled_pair,
          }"
        >
          <section class="mesh-direction">
            <div class="mesh-direction__head">
              <div class="mesh-direction__identity">
                <div class="mesh-direction__title-row">
                  <div class="mesh-direction__title">{{ directionTitle(connection.forward, t('mesh.localToPeer')) }}</div>
                  <el-tag v-if="connection.duplicate_enabled_pair" type="danger" size="small">
                    {{ t('mesh.duplicateLinkPair') }}
                  </el-tag>
                  <el-tag v-if="connection.integrity_status === 'broken'" type="danger" size="small">
                    {{ t('mesh.connectionBroken') }}
                  </el-tag>
                  <el-tag v-if="connection.peer_disabled" type="info" size="small">
                    {{ t('mesh.peerNodeDisabled') }}
                  </el-tag>
                  <el-tag :type="connection.has_preshared_key ? 'success' : 'info'" size="small">
                    {{ connection.has_preshared_key ? t('mesh.pskConfigured') : t('mesh.pskMissing') }}
                  </el-tag>
                </div>
                <p v-if="connection.integrity_status === 'broken' && connection.integrity_message" class="mesh-direction__integrity">
                  {{ meshText(connection.integrity_message) }}
                </p>
                <p v-if="connection.duplicate_enabled_pair && connection.duplicate_message" class="mesh-direction__integrity">
                  {{ meshText(connection.duplicate_message) }}
                </p>
              </div>
              <div class="mesh-direction__actions">
                <div class="peer-switch">
                  <span>{{ connection.enabled ? t('common.enabled') : t('common.disabled') }}</span>
                  <el-switch
                    size="small"
                    :model-value="connection.enabled"
                    :loading="connectionToggleLoading(connection.link_group_id)"
                    :disabled="readonlyMesh || connection.readonly || connectionToggleLoading(connection.link_group_id)"
                    @change="(value: boolean | string | number) => toggleConnection(connection, Boolean(value))"
                  />
                </div>
                <el-button :icon="EditPen" plain size="small" :disabled="readonlyMesh || connection.readonly" @click="openEdit(connection)">{{ t('mesh.editParams') }}</el-button>
              </div>
            </div>
            <dl>
              <div>
                <dt>AllowedIPs</dt>
                <dd>{{ connection.forward.allowed_ips }}</dd>
              </div>
              <div>
                <dt>Endpoint</dt>
                <dd>{{ endpointModeLabel[connection.forward.endpoint_mode] }} · {{ meshText(connection.forward.endpoint_summary) }}</dd>
              </div>
              <div>
                <dt>Keepalive</dt>
                <dd>{{ connection.forward.keepalive_display }}</dd>
              </div>
              <div>
                <dt>{{ t('mesh.addressFamily') }}</dt>
                <dd>{{ connection.forward.endpoint_ref_family?.toUpperCase() || t('common.none') }}</dd>
              </div>
            </dl>
          </section>
        </article>
      </div>
      <div v-else class="empty-state">{{ t('mesh.noConnections') }}</div>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Plus /></el-icon></span>
        <div>
          <h3>{{ dialogMode === 'create' ? t('mesh.createPeer') : t('mesh.editPeer') }}</h3>
          <p>{{ t('mesh.dialogDescription') }}</p>
        </div>
      </div>
      <el-form ref="formRef" v-loading="draftLoading" :model="form" :rules="formRules" class="dialog-form" label-position="top">
        <el-form-item :label="t('mesh.localNode')">
          <el-input :model-value="currentNode?.name || currentNodeId" disabled />
        </el-form-item>
        <el-form-item :label="t('mesh.peerNode')" prop="peer_node_id" required>
          <el-select v-if="dialogMode === 'create'" v-model="form.peer_node_id" style="width: 100%">
            <el-option
              v-for="node in peerOptions"
              :key="node.id"
              :value="node.id"
              :label="`${node.name} · ${nodeTypeLabel(node.node_type)} · IPv4 ${node.ipv4_address || t('nodeWorkspace.unset')} · IPv6 ${node.ipv6_address || t('nodeWorkspace.unset')}`"
            />
          </el-select>
          <el-input v-else :model-value="selectedPeer?.name || form.peer_node_id" disabled />
        </el-form-item>
        <el-form-item :label="t('mesh.endpointFamily')">
          <el-segmented
            v-model="form.endpoint_ref_family"
            :options="[
              { label: 'IPv4', value: 'ipv4' },
              { label: 'IPv6', value: 'ipv6' },
            ]"
          />
          <p class="field-hint">{{ t('mesh.endpointFamilyHint') }}</p>
        </el-form-item>
        <div v-if="draftWarnings.length" class="draft-warnings">
          <span v-for="item in draftWarnings" :key="item">{{ meshText(item) }}</span>
        </div>

        <section class="connection-panel">
          <div class="connection-panel__head">
            <strong>{{ t('mesh.forwardConfig') }}</strong>
            <span>{{ currentNode?.name || t('mesh.currentNode') }} -> {{ selectedPeer?.name || t('mesh.peerNode') }}</span>
          </div>
          <el-form-item :label="t('mesh.forwardAllowedIps')" prop="forward_allowed_ips" required>
            <el-input v-model="form.forward_allowed_ips" :placeholder="t('mesh.defaultPeerVirtualIp')" />
          </el-form-item>
          <div class="form-grid">
            <el-form-item :label="t('mesh.forwardKeepalive')">
              <el-input-number v-model="form.forward_persistent_keepalive" :min="0" :max="65535" style="width: 100%" />
            </el-form-item>
            <el-form-item :label="t('mesh.forwardEndpoint')">
              <el-select v-model="form.forward_endpoint_mode" style="width: 100%">
                <el-option :label="t('mesh.auto')" value="auto" />
                <el-option :label="t('mesh.noneEndpoint')" value="none" />
                <el-option :label="t('mesh.manualDeprecated')" value="manual" />
              </el-select>
            </el-form-item>
          </div>
          <p class="endpoint-summary">
            {{ forwardEndpointSummaryText }}
          </p>
          <div v-if="form.forward_endpoint_mode === 'manual'" class="form-grid">
            <el-form-item :label="t('mesh.forwardManualHost')" prop="forward_manual_host" required>
              <el-input v-model="form.forward_manual_host" :placeholder="t('mesh.ipOrDomain')" />
            </el-form-item>
            <el-form-item :label="t('mesh.forwardManualPort')" prop="forward_manual_port" required>
              <el-input-number v-model="form.forward_manual_port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </div>
        </section>

        <section class="connection-panel">
          <div class="connection-panel__head">
            <strong>{{ t('mesh.reverseConfig') }}</strong>
            <span>{{ selectedPeer?.name || t('mesh.peerNode') }} -> {{ currentNode?.name || t('mesh.currentNode') }}</span>
          </div>
          <el-form-item :label="t('mesh.reverseAllowedIps')" prop="reverse_allowed_ips" required>
            <el-input v-model="form.reverse_allowed_ips" :placeholder="t('mesh.defaultCurrentVirtualIp')" />
          </el-form-item>
          <div class="form-grid">
            <el-form-item :label="t('mesh.reverseKeepalive')">
              <el-input-number v-model="form.reverse_persistent_keepalive" :min="0" :max="65535" style="width: 100%" />
            </el-form-item>
            <el-form-item :label="t('mesh.reverseEndpoint')">
              <el-select v-model="form.reverse_endpoint_mode" style="width: 100%">
                <el-option :label="t('mesh.auto')" value="auto" />
                <el-option :label="t('mesh.noneEndpoint')" value="none" />
                <el-option :label="t('mesh.manualDeprecated')" value="manual" />
              </el-select>
            </el-form-item>
          </div>
          <p class="endpoint-summary">
            {{ reverseEndpointSummaryText }}
          </p>
          <div v-if="form.reverse_endpoint_mode === 'manual'" class="form-grid">
            <el-form-item :label="t('mesh.reverseManualHost')" prop="reverse_manual_host" required>
              <el-input v-model="form.reverse_manual_host" :placeholder="t('mesh.ipOrDomain')" />
            </el-form-item>
            <el-form-item :label="t('mesh.reverseManualPort')" prop="reverse_manual_port" required>
              <el-input-number v-model="form.reverse_manual_port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </div>
        </section>

        <section class="connection-panel">
          <div class="connection-panel__head">
            <strong>{{ t('mesh.security') }}</strong>
            <span>{{ t('mesh.pskDescription') }}</span>
          </div>
          <el-form-item :label="t('mesh.psk')">
            <el-input v-model="form.preshared_key" :placeholder="t('mesh.nullable')">
              <template #append>
                <el-button :icon="Key" :loading="generatingPsk" @click="generatePsk">{{ t('mesh.autoGenerate') }}</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="t('mesh.notes')"><el-input v-model="form.notes" type="textarea" /></el-form-item>
          <div class="switch-row">
            <div>
              <strong>{{ t('mesh.enableConnection') }}</strong>
              <span>{{ t('mesh.enableConnectionDescription') }}</span>
            </div>
            <el-switch v-model="form.enabled" />
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button
          v-if="dialogMode === 'edit'"
          type="danger"
          plain
          :icon="Delete"
          :loading="deletingConnection"
          :disabled="readonlyMesh"
          @click="deleteConnection"
        >
          {{ t('common.delete') }}
        </el-button>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creatingConnection" :disabled="readonlyMesh" @click="submit">{{ submitText }}</el-button>
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
.mesh-card--broken .mesh-direction { border-color: var(--app-danger-border); background: color-mix(in srgb, var(--app-danger-soft) 45%, var(--app-surface)); }
.mesh-card--disabled .mesh-direction {
  background: var(--app-surface-sunken);
  box-shadow: none;
}
.mesh-card--disabled .mesh-direction__title,
.mesh-card--disabled .mesh-direction dd,
.mesh-card--disabled .peer-switch {
  color: var(--app-faint);
}
.mesh-card--disabled .mesh-direction dt,
.mesh-card--disabled .mesh-direction__actions {
  opacity: 0.72;
}
.peer-switch { display: inline-flex; align-items: center; gap: 7px; min-height: 30px; padding: 4px 8px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); color: color-mix(in srgb, var(--app-text) 70%, var(--app-muted)); font-size: 12px; font-weight: 750; }
.mesh-direction { padding: 10px 12px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.mesh-direction__head { display: grid; grid-template-columns: minmax(180px, 1fr) auto; align-items: center; gap: 10px; }
.mesh-direction__identity { min-width: 0; }
.mesh-direction__title-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.mesh-direction__title { color: var(--app-text-strong); font-size: 17px; font-weight: 850; line-height: 1.25; }
.mesh-direction__integrity { margin: 6px 0 0; color: var(--app-danger-text); font-size: 13px; line-height: 1.45; }
.mesh-direction__actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.mesh-direction dl { display: grid; grid-template-columns: minmax(150px, 1fr) minmax(220px, 1.5fr) minmax(80px, 0.6fr) minmax(70px, 0.5fr); gap: 10px; margin: 10px 0 0; }
.mesh-direction dt { color: var(--app-faint); font-size: 12px; font-weight: 650; }
.mesh-direction dd { margin: 4px 0 0; overflow: hidden; color: var(--app-text-strong); font-size: 13px; font-weight: 700; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { display: grid; place-items: center; min-height: 170px; border: 1px dashed var(--app-border-strong); border-radius: 8px; background: color-mix(in srgb, var(--app-overlay) 85%, transparent); color: var(--app-muted); }
.dialog-intro { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); }
.dialog-intro__icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 42px; height: 42px; border: 1px solid var(--app-border-accent); border-radius: 8px; background: var(--app-primary-soft); color: var(--app-primary); }
.dialog-intro h3 { margin: 0; color: var(--app-text); }
.dialog-intro p { margin: 5px 0 0; color: var(--app-muted); line-height: 1.5; }
.dialog-form { display: grid; gap: 2px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.field-hint { margin: 8px 0 0; color: var(--app-muted); font-size: 13px; line-height: 1.5; }
.draft-warnings { display: grid; gap: 6px; margin: 0 0 10px; padding: 10px 12px; border: 1px solid var(--app-warning-border); border-radius: 8px; background: var(--app-warning-soft); color: var(--app-warning-text); font-size: 13px; line-height: 1.5; }
.connection-panel { display: grid; gap: 2px; margin: 8px 0 12px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-elevated); }
.connection-panel__head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; color: var(--app-text); }
.connection-panel__head span { color: var(--app-muted); font-size: 13px; }
.endpoint-summary { margin: -2px 0 12px; padding: 9px 10px; border-radius: 8px; background: var(--app-info-soft); color: color-mix(in srgb, var(--app-text) 70%, var(--app-muted)); font-size: 13px; line-height: 1.5; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface); }
.switch-row strong, .switch-row span { display: block; }
.switch-row strong { color: var(--app-text); }
.switch-row span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
@media (max-width: 980px) {
  .mesh-direction dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } .mesh-direction__head { grid-template-columns: 1fr; } .mesh-direction__actions { justify-content: flex-start; } }
@media (max-width: 720px) { .form-grid, .mesh-direction dl { grid-template-columns: 1fr; } }
</style>
