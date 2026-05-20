<script setup lang="ts">
import { ArrowLeft, Connection, Finished, WarningFilled } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead, EndpointRefFamily, NodeRead, QuickMeshGenerateRead, QuickMeshMode } from '@/types/api'
import { notify } from '@/utils/notify'

const props = defineProps<{
  mode: QuickMeshMode
}>()

const router = useRouter()
const { t } = useI18n()

const configs = shallowRef<ConfigRead[]>([])
const nodes = shallowRef<NodeRead[]>([])
const selectedConfigId = shallowRef('')
const endpointFamily = shallowRef<EndpointRefFamily>('ipv4')
const hubNodeId = shallowRef('')
const gatewayNodeIds = shallowRef<string[]>([])
const leafAssignments = reactive<Record<string, string>>({})
const usePresharedKey = shallowRef(false)
const loading = shallowRef(false)
const generating = shallowRef(false)
const loadError = shallowRef('')
const result = shallowRef<QuickMeshGenerateRead | null>(null)

const isHubSpoke = computed(() => props.mode === 'hub_spoke')
const isFullMesh = computed(() => props.mode === 'full_mesh')
const isFreeMesh = computed(() => props.mode === 'free_mesh')
const title = computed(() => {
  if (isHubSpoke.value) return t('tools.quickMesh.hubSpokeTitle')
  if (isFreeMesh.value) return t('tools.quickMesh.freeMeshTitle')
  return t('tools.quickMesh.fullMeshTitle')
})
const description = computed(() => {
  if (isHubSpoke.value) return t('tools.quickMesh.hubSpokeDescription')
  if (isFreeMesh.value) return t('tools.quickMesh.freeMeshDescription')
  return t('tools.quickMesh.fullMeshDescription')
})
const selectedConfig = computed(() => configs.value.find((item) => item.id === selectedConfigId.value) || null)
const enabledNodes = computed(() => nodes.value.filter((node) => node.enabled))
const endpointKey = computed(() => (endpointFamily.value === 'ipv6' ? 'ipv6_address' : 'ipv4_address'))
const hubCandidates = computed(() => enabledNodes.value.filter((node) => Boolean(node[endpointKey.value])))
const selectedHub = computed(() => hubCandidates.value.find((node) => node.id === hubNodeId.value) || null)
const selectedGatewayNodes = computed(() => gatewayNodeIds.value.map((nodeId) => enabledNodes.value.find((node) => node.id === nodeId)).filter((node): node is NodeRead => Boolean(node)))
const freeLeafNodes = computed(() => enabledNodes.value.filter((node) => !gatewayNodeIds.value.includes(node.id)))
const assignedLeafNodes = computed(() => freeLeafNodes.value.filter((node) => Boolean(leafAssignments[node.id])))
const unassignedLeafNodes = computed(() => freeLeafNodes.value.filter((node) => !leafAssignments[node.id]))
const invalidLeafAssignments = computed(() => Object.entries(leafAssignments).filter(([leafId, gatewayId]) => {
  return !freeLeafNodes.value.some((node) => node.id === leafId) || !gatewayNodeIds.value.includes(gatewayId)
}))
const missingVirtualIpNodes = computed(() => enabledNodes.value.filter((node) => !node.virtual_ip))
const missingPublicNodes = computed(() => {
  if (!isFullMesh.value) {
    return []
  }
  return enabledNodes.value.filter((node) => !node[endpointKey.value])
})
const issueItems = computed(() => [
  ...missingVirtualIpNodes.value.map((node) => t('tools.quickMesh.issueVirtualIp', { name: node.name })),
  ...missingPublicNodes.value.map((node) => t('tools.quickMesh.issuePublic', { name: node.name, family: endpointFamily.value.toUpperCase() })),
  ...(isHubSpoke.value && !selectedHub.value ? [t('tools.quickMesh.issueHubPublic', { family: endpointFamily.value.toUpperCase() })] : []),
  ...(isFreeMesh.value && !gatewayNodeIds.value.length ? [t('tools.quickMesh.issueGatewayRequired')] : []),
  ...(isFreeMesh.value ? unassignedLeafNodes.value.map((node) => t('tools.quickMesh.issueLeafUnassigned', { name: node.name })) : []),
  ...(isFreeMesh.value && invalidLeafAssignments.value.length ? [t('tools.quickMesh.issueInvalidLeafAssignment')] : []),
])
const expectedGroups = computed(() => {
  const count = enabledNodes.value.length
  if (count < 2) return 0
  if (isHubSpoke.value) return count - 1
  if (isFreeMesh.value) {
    const gatewayCount = gatewayNodeIds.value.length
    return (gatewayCount * (gatewayCount - 1)) / 2 + assignedLeafNodes.value.length
  }
  return (count * (count - 1)) / 2
})
const canGenerate = computed(() =>
  Boolean(
    selectedConfig.value
      && enabledNodes.value.length >= 2
      && !missingVirtualIpNodes.value.length
      && !missingPublicNodes.value.length
      && (!isHubSpoke.value || selectedHub.value)
      && (!isFreeMesh.value || (gatewayNodeIds.value.length && !unassignedLeafNodes.value.length && !invalidLeafAssignments.value.length))
  ),
)
const statusTitle = computed(() => {
  if (!selectedConfig.value) return t('tools.quickMesh.status.noConfig')
  if (enabledNodes.value.length < 2) return t('tools.quickMesh.status.notEnoughNodes')
  if (isHubSpoke.value && !selectedHub.value) return t('tools.quickMesh.status.noHub')
  if (isFreeMesh.value && !gatewayNodeIds.value.length) return t('tools.quickMesh.status.noGateway')
  if (isFreeMesh.value && unassignedLeafNodes.value.length) return t('tools.quickMesh.status.unassignedLeaf')
  if (missingVirtualIpNodes.value.length) return t('tools.quickMesh.status.missingVirtualIp')
  if (missingPublicNodes.value.length) return t('tools.quickMesh.status.missingPublic')
  return t('tools.quickMesh.status.ready')
})
const statusDescription = computed(() => {
  if (!canGenerate.value) return t('tools.quickMesh.status.fixBeforeGenerate')
  return t('tools.quickMesh.status.readyDescription', { count: expectedGroups.value })
})

function backToQuickMeshTools() {
  void router.push('/tools/quick-mesh')
}

function nodeEndpointText(node: NodeRead) {
  const host = node[endpointKey.value]
  return host ? `${host}:${node.listen_port || selectedConfig.value?.default_listen_port || '-'}` : t('tools.quickMesh.noPublicAddress')
}

function clearLeafAssignments() {
  Object.keys(leafAssignments).forEach((nodeId) => {
    delete leafAssignments[nodeId]
  })
}

function setGatewayNodeIds(nextIds: string[]) {
  if (nextIds.length === gatewayNodeIds.value.length && nextIds.every((nodeId, index) => nodeId === gatewayNodeIds.value[index])) {
    return
  }
  gatewayNodeIds.value = nextIds
}

function applyDefaultFreeMeshTopology() {
  clearLeafAssignments()
  if (!isFreeMesh.value) return
  const defaultGatewayIds = hubCandidates.value.map((node) => node.id)
  const firstGatewayId = defaultGatewayIds[0]
  setGatewayNodeIds(defaultGatewayIds)
  if (!firstGatewayId) return
  enabledNodes.value.forEach((node) => {
    if (!defaultGatewayIds.includes(node.id)) {
      leafAssignments[node.id] = firstGatewayId
    }
  })
}

function normalizeFreeMeshTopology() {
  if (!isFreeMesh.value) return
  const candidateIds = new Set(hubCandidates.value.map((node) => node.id))
  const validGatewayIds = gatewayNodeIds.value.filter((nodeId) => candidateIds.has(nodeId))
  setGatewayNodeIds(validGatewayIds)

  const enabledIds = new Set(enabledNodes.value.map((node) => node.id))
  Object.keys(leafAssignments).forEach((leafId) => {
    if (!enabledIds.has(leafId) || gatewayNodeIds.value.includes(leafId) || !gatewayNodeIds.value.includes(leafAssignments[leafId])) {
      delete leafAssignments[leafId]
    }
  })

  const fallbackGateway = gatewayNodeIds.value[0]
  if (!fallbackGateway) return
  freeLeafNodes.value.forEach((node) => {
    if (!leafAssignments[node.id]) {
      leafAssignments[node.id] = fallbackGateway
    }
  })
}

async function loadConfigs() {
  loading.value = true
  loadError.value = ''
  try {
    configs.value = await api.configs()
    selectedConfigId.value = configs.value[0]?.id || ''
  } catch (error) {
    loadError.value = error instanceof ApiClientError ? error.message : t('tools.quickMesh.loadFailed')
  } finally {
    loading.value = false
  }
}

async function loadNodes(configId: string) {
  if (!configId) {
    nodes.value = []
    hubNodeId.value = ''
    return
  }
  loading.value = true
  loadError.value = ''
  result.value = null
  try {
    nodes.value = await api.nodes(configId)
    hubNodeId.value = enabledNodes.value[0]?.id || ''
    applyDefaultFreeMeshTopology()
  } catch (error) {
    loadError.value = error instanceof ApiClientError ? error.message : t('tools.quickMesh.loadFailed')
  } finally {
    loading.value = false
  }
}

async function generateMesh() {
  if (!selectedConfig.value || !canGenerate.value || generating.value) return
  try {
    await ElMessageBox.confirm(
      t('tools.quickMesh.confirmMessage', { name: selectedConfig.value.name, mode: title.value }),
      t('tools.quickMesh.confirmTitle'),
      {
        type: 'warning',
        confirmButtonText: t('tools.quickMesh.confirmAction'),
        cancelButtonText: t('common.cancel'),
      },
    )
  } catch {
    return
  }

  generating.value = true
  result.value = null
  try {
    result.value = await api.quickGenerateMesh(selectedConfig.value.id, {
      mode: props.mode,
      endpoint_ref_family: endpointFamily.value,
      hub_node_id: isHubSpoke.value ? hubNodeId.value : undefined,
      gateway_node_ids: isFreeMesh.value ? gatewayNodeIds.value : undefined,
      leaf_assignments: isFreeMesh.value ? { ...leafAssignments } : undefined,
      use_preshared_key: usePresharedKey.value,
    })
    notify.success(t('tools.quickMesh.generated', { count: result.value.generated_groups }))
    await loadNodes(selectedConfig.value.id)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('tools.quickMesh.generateFailed'))
  } finally {
    generating.value = false
  }
}

watch(selectedConfigId, (configId) => {
  void loadNodes(configId)
})

watch(hubCandidates, (items) => {
  if (!items.some((node) => node.id === hubNodeId.value)) {
    hubNodeId.value = items[0]?.id || ''
  }
  normalizeFreeMeshTopology()
})

watch(gatewayNodeIds, () => {
  normalizeFreeMeshTopology()
})

watch(() => props.mode, () => {
  result.value = null
  if (isFreeMesh.value) {
    applyDefaultFreeMeshTopology()
  } else {
    gatewayNodeIds.value = []
    clearLeafAssignments()
  }
})

onMounted(() => {
  void loadConfigs()
})
</script>

<template>
  <section class="quick-generate-page">
    <div v-if="generating" class="quick-generate-overlay" role="status" aria-live="assertive">
      <el-icon class="quick-generate-overlay__spinner"><Connection /></el-icon>
      <strong>{{ t('tools.quickMesh.generating') }}</strong>
      <span>{{ t('tools.quickMesh.generatingDescription') }}</span>
    </div>

    <div class="tool-hero">
      <div class="tool-hero__copy">
        <el-button class="tool-hero__back" :icon="ArrowLeft" plain :disabled="generating" @click="backToQuickMeshTools">{{ t('tools.quickMesh.back') }}</el-button>
        <div>
          <p class="tool-hero__eyebrow">{{ t('tools.quickMesh.title') }}</p>
          <h1>{{ title }}</h1>
          <p>{{ description }}</p>
        </div>
      </div>
      <el-icon><Connection /></el-icon>
    </div>

    <div v-if="loading && !selectedConfig" class="content-band view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError" class="content-band view-feedback view-feedback--error">{{ loadError }}</div>
    <div v-else class="quick-generate-layout">
      <section class="quick-generate-panel">
        <div class="quick-generate-warning">
          <el-icon><WarningFilled /></el-icon>
          <div>
            <strong>{{ t('tools.quickMesh.dangerTitle') }}</strong>
            <p>{{ t('tools.quickMesh.dangerDescription') }}</p>
          </div>
        </div>

        <div class="quick-generate-section">
          <div class="section-title">
            <h2>{{ t('tools.quickMesh.parameters') }}</h2>
            <p>{{ t('tools.quickMesh.parametersDescription') }}</p>
          </div>
          <el-form label-position="top">
            <el-form-item :label="t('tools.quickMesh.config')">
              <el-select v-model="selectedConfigId" :placeholder="t('tools.quickMesh.noConfigs')" :disabled="generating || !configs.length">
                <el-option v-for="config in configs" :key="config.id" :label="config.name" :value="config.id" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('tools.quickMesh.endpointFamily')">
              <el-radio-group v-model="endpointFamily" :disabled="generating">
                <el-radio-button label="ipv4">IPv4</el-radio-button>
                <el-radio-button label="ipv6">IPv6</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="isHubSpoke" :label="t('tools.quickMesh.hubNode')">
              <el-select v-model="hubNodeId" :placeholder="t('tools.quickMesh.noHubNodes')" :disabled="generating || !hubCandidates.length">
                <el-option v-for="node in hubCandidates" :key="node.id" :label="node.name" :value="node.id" />
              </el-select>
            </el-form-item>
            <template v-if="isFreeMesh">
              <el-form-item :label="t('tools.quickMesh.gatewayNodes')">
                <el-select v-model="gatewayNodeIds" multiple :placeholder="t('tools.quickMesh.noGatewayNodes')" :disabled="generating || !hubCandidates.length">
                  <el-option v-for="node in hubCandidates" :key="node.id" :label="node.name" :value="node.id" />
                </el-select>
              </el-form-item>
              <div class="free-mesh-editor">
                <div class="free-mesh-editor__head">
                  <h3>{{ t('tools.quickMesh.leafAssignments') }}</h3>
                  <p>{{ t('tools.quickMesh.leafAssignmentsDescription') }}</p>
                </div>
                <div v-if="!freeLeafNodes.length" class="free-mesh-editor__empty">{{ t('tools.quickMesh.noLeafNodes') }}</div>
                <article v-for="node in freeLeafNodes" :key="node.id" class="free-leaf-row">
                  <div>
                    <strong>{{ node.name }}</strong>
                    <span>{{ node.virtual_ip || t('tools.quickMesh.noVirtualIp') }}</span>
                  </div>
                  <el-select v-model="leafAssignments[node.id]" :placeholder="t('tools.quickMesh.selectGateway')" :disabled="generating || !selectedGatewayNodes.length">
                    <el-option v-for="gateway in selectedGatewayNodes" :key="gateway.id" :label="gateway.name" :value="gateway.id" />
                  </el-select>
                </article>
              </div>
            </template>
            <el-form-item :label="t('tools.quickMesh.psk')">
              <div class="quick-switch-row">
                <div>
                  <strong>{{ t('tools.quickMesh.pskTitle') }}</strong>
                  <span>{{ t('tools.quickMesh.pskDescription') }}</span>
                </div>
                <el-switch v-model="usePresharedKey" :disabled="generating" />
              </div>
            </el-form-item>
          </el-form>
        </div>

        <div v-if="issueItems.length" class="issue-list">
          <h3>{{ t('tools.quickMesh.issues') }}</h3>
          <p v-for="item in issueItems" :key="item">{{ item }}</p>
        </div>

        <el-button type="danger" size="large" :icon="Connection" :loading="generating" :disabled="!canGenerate" @click="generateMesh">
          {{ t('tools.quickMesh.generateAction') }}
        </el-button>
      </section>

      <aside class="quick-generate-panel quick-generate-panel--summary">
        <div class="summary-head">
          <el-icon><Finished /></el-icon>
          <div>
            <h2>{{ statusTitle }}</h2>
            <p>{{ statusDescription }}</p>
          </div>
        </div>
        <dl class="summary-grid">
          <div>
            <dt>{{ t('tools.quickMesh.enabledNodes') }}</dt>
            <dd>{{ enabledNodes.length }}</dd>
          </div>
          <div>
            <dt>{{ t('tools.quickMesh.expectedGroups') }}</dt>
            <dd>{{ expectedGroups }}</dd>
          </div>
          <div v-if="isFreeMesh">
            <dt>{{ t('tools.quickMesh.gatewayCount') }}</dt>
            <dd>{{ gatewayNodeIds.length }}</dd>
          </div>
          <div v-if="isFreeMesh">
            <dt>{{ t('tools.quickMesh.leafCount') }}</dt>
            <dd>{{ assignedLeafNodes.length }}</dd>
          </div>
          <div>
            <dt>{{ t('tools.quickMesh.addressFamily') }}</dt>
            <dd>{{ endpointFamily.toUpperCase() }}</dd>
          </div>
          <div v-if="result">
            <dt>{{ t('tools.quickMesh.deletedLinks') }}</dt>
            <dd>{{ result.deleted_links }}</dd>
          </div>
          <div>
            <dt>{{ t('tools.quickMesh.psk') }}</dt>
            <dd>{{ usePresharedKey ? t('tools.quickMesh.pskEnabled') : t('tools.quickMesh.pskDisabled') }}</dd>
          </div>
        </dl>

        <div class="node-list">
          <h3>{{ t('tools.quickMesh.participatingNodes') }}</h3>
          <div v-if="!enabledNodes.length" class="node-list__empty">{{ t('tools.quickMesh.noEnabledNodes') }}</div>
          <article v-for="node in enabledNodes" :key="node.id" class="node-row">
            <div>
              <strong>{{ node.name }}</strong>
              <span>{{ node.virtual_ip || t('tools.quickMesh.noVirtualIp') }}</span>
            </div>
            <em>{{ nodeEndpointText(node) }}</em>
          </article>
        </div>

      </aside>
    </div>
  </section>
</template>

<style scoped>
.quick-generate-page { position: relative; display: grid; gap: 18px; }
.tool-hero {
  display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 172px; padding: 28px 32px;
  border: 1px solid var(--app-border); border-radius: 18px; background: linear-gradient(135deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}
.tool-hero__copy { display: grid; gap: 18px; }
.tool-hero__back { justify-self: start; }
.tool-hero__eyebrow { margin: 0 0 10px; color: var(--app-primary-strong); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.tool-hero h1 { margin: 0; color: var(--app-text-strong); font-size: 34px; letter-spacing: 0; }
.tool-hero p { max-width: 620px; margin: 10px 0 0; color: var(--app-muted); }
.tool-hero > .el-icon { flex: 0 0 auto; width: 86px; height: 86px; border-radius: 18px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 42px; }
.quick-generate-layout { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(360px, .95fr); gap: 18px; }
.quick-generate-panel {
  display: grid; align-content: start; gap: 18px; padding: 24px; border: 1px solid var(--app-border); border-radius: 14px;
  background: var(--app-surface); box-shadow: var(--app-shadow-sm);
}
.quick-generate-warning {
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 14px; padding: 16px;
  border: 1px solid rgba(210, 76, 76, .34); border-radius: 12px; background: rgba(210, 76, 76, .08);
}
.quick-generate-warning .el-icon { color: var(--el-color-danger); font-size: 24px; }
.quick-generate-warning strong { color: var(--app-text-strong); }
.quick-generate-warning p { margin: 6px 0 0; color: var(--app-muted); line-height: 1.65; }
.quick-generate-section { display: grid; gap: 16px; }
.quick-switch-row {
  display: flex; align-items: center; justify-content: space-between; gap: 16px; width: 100%; padding: 14px 16px;
  border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface-elevated);
}
.quick-switch-row div { display: grid; gap: 4px; min-width: 0; }
.quick-switch-row strong { color: var(--app-text-strong); }
.quick-switch-row span { color: var(--app-muted); line-height: 1.55; }
.free-mesh-editor {
  display: grid; gap: 12px; padding: 14px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface-elevated);
}
.free-mesh-editor__head { display: grid; gap: 4px; }
.free-mesh-editor__head h3 { margin: 0; color: var(--app-text-strong); letter-spacing: 0; }
.free-mesh-editor__head p,
.free-mesh-editor__empty { margin: 0; color: var(--app-muted); line-height: 1.6; }
.free-leaf-row {
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(180px, 240px); gap: 12px; align-items: center;
  padding: 12px; border: 1px solid var(--app-border); border-radius: 10px; background: var(--app-surface);
}
.free-leaf-row div { display: grid; gap: 4px; min-width: 0; }
.free-leaf-row strong { overflow: hidden; color: var(--app-text-strong); text-overflow: ellipsis; white-space: nowrap; }
.free-leaf-row span { color: var(--app-muted); font-size: 13px; }
.section-title h2,
.summary-head h2,
.node-list h3,
.issue-list h3 { margin: 0; color: var(--app-text-strong); letter-spacing: 0; }
.section-title p,
.summary-head p { margin: 6px 0 0; color: var(--app-muted); line-height: 1.65; }
.summary-head { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 14px; align-items: start; }
.summary-head .el-icon {
  display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 10px;
  color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 24px;
}
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
.summary-grid div { padding: 14px; border: 1px solid var(--app-border); border-radius: 10px; background: var(--app-surface-elevated); }
.summary-grid dt { color: var(--app-muted); font-size: 12px; font-weight: 800; }
.summary-grid dd { margin: 6px 0 0; color: var(--app-text-strong); font-size: 22px; font-weight: 850; }
.node-list,
.issue-list { display: grid; gap: 10px; }
.node-list__empty { color: var(--app-muted); }
.node-row {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px;
  border: 1px solid var(--app-border); border-radius: 10px; background: var(--app-surface-elevated);
}
.node-row div { display: grid; gap: 4px; min-width: 0; }
.node-row strong { color: var(--app-text-strong); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-row span,
.node-row em { color: var(--app-muted); font-style: normal; font-size: 13px; }
.issue-list { padding: 14px; border: 1px solid rgba(210, 76, 76, .26); border-radius: 12px; background: rgba(210, 76, 76, .06); }
.issue-list p { margin: 0; color: var(--el-color-danger); line-height: 1.6; }
.quick-generate-overlay {
  position: fixed; inset: 0; z-index: 1000; display: grid; place-content: center; gap: 12px; text-align: center;
  background: rgba(245, 248, 247, .78); backdrop-filter: blur(8px); color: var(--app-text-strong);
}
.quick-generate-overlay__spinner { justify-self: center; font-size: 36px; color: var(--app-primary-strong); animation: quick-spin 1s linear infinite; }
.quick-generate-overlay span { color: var(--app-muted); }
@keyframes quick-spin { to { transform: rotate(360deg); } }
@media (max-width: 1100px) {
  .quick-generate-layout { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .tool-hero { align-items: flex-start; padding: 24px; }
  .tool-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .summary-grid { grid-template-columns: 1fr; }
  .free-leaf-row { grid-template-columns: 1fr; }
  .node-row { align-items: flex-start; flex-direction: column; }
}
</style>
