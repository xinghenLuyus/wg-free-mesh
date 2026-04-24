<script setup lang="ts">
import { Check, Document, EditPen, Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import { useRealtime } from '@/composables/useRealtime'
import { translateMeshText } from '@/utils/meshText'
import { toNodeUpdatePayload } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'
import type { NodeApplyUpdatedPayload, RealtimeEvent, SyncStatusRead } from '@/types/api'

const route = useRoute()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const syncingNode = actions.isPending('sync-node')
const savingApplied = actions.isPending('save-applied')

const syncStatus = shallowRef<SyncStatusRead | null>(null)
const previewContent = shallowRef('')
const loading = shallowRef(false)
const loadError = shallowRef('')
const autoSyncSaving = shallowRef(false)
let loadTicket = 0
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'node.apply.updated') return
  const payload = event.payload as unknown as NodeApplyUpdatedPayload
  if (payload.config_id !== String(route.params.configId) || payload.node_id !== currentNodeId.value) return
  syncStatus.value = payload.sync_status
  previewContent.value = payload.preview.content
  Object.assign(appliedState, payload.applied)
})
const appliedState = reactive({
  content: '',
  exists: false,
  node_name: '',
  node_type: '',
  desired_version: 0,
  staged_version: 0,
})

const currentNodeId = computed(() => String(route.params.nodeId))
const topologyBlocked = computed(() => syncStatus.value ? !syncStatus.value.topology_valid : false)
const topologyMessages = computed(() => syncStatus.value?.topology_messages ?? [])

function meshText(message: string) {
  return translateMeshText(message, t)
}

async function loadNodeState() {
  const ticket = ++loadTicket
  loading.value = true
  loadError.value = ''
  const configId = String(route.params.configId)
  const nodeId = currentNodeId.value
  try {
    const [status, preview, applied] = await Promise.all([
      api.nodeSyncStatus(configId, nodeId),
      api.wgPreview(configId, nodeId),
      api.readAppliedConf(configId, nodeId),
    ])
    if (ticket !== loadTicket) return
    syncStatus.value = status
    previewContent.value = preview.content
    Object.assign(appliedState, applied)
  } catch (error) {
    if (ticket !== loadTicket) return
    loadError.value = error instanceof ApiClientError ? error.message : t('apply.loadFailed')
    throw error
  } finally {
    if (ticket === loadTicket) loading.value = false
  }
}

async function saveApplied() {
  const configId = String(route.params.configId)
  await actions.run('save-applied', async () => {
    try {
      await api.saveAppliedConf(configId, currentNodeId.value, appliedState.content)
      await loadNodeState()
      notify.success(t('apply.stagedSaved'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('apply.saveFailed'))
    }
  })
}

async function syncNode() {
  const configId = String(route.params.configId)
  await actions.run('sync-node', async () => {
    try {
      await api.syncNode(configId, currentNodeId.value)
      await loadNodeState()
      notify.success(t('apply.synced'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('apply.syncFailed'))
    }
  })
}

async function toggleAutoSync(nextValue: boolean | string | number) {
  const enabled = Boolean(nextValue)
  const nodeId = currentNodeId.value
  try {
    autoSyncSaving.value = true
    const currentNode = await api.node(nodeId)
    await api.updateNode(nodeId, toNodeUpdatePayload(currentNode, { auto_sync: enabled }))
    await loadNodeState()
    notify.success(enabled ? t('apply.autoSyncEnabledToast') : t('apply.autoSyncDisabledToast'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('apply.autoSyncSaveFailed'))
  } finally {
    autoSyncSaving.value = false
  }
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    try {
      await loadNodeState()
    } catch {
      notify.error(loadError.value || t('apply.loadFailed'))
    }
  },
)

onMounted(async () => {
  try {
    await loadNodeState()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('apply.loadFailed'))
  }
})
</script>

<template>
  <section class="node-template">
    <div v-if="loading && !syncStatus" class="content-band view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !syncStatus" class="content-band view-feedback view-feedback--error">{{ loadError }}</div>
    <div v-else-if="syncStatus" class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>{{ t('apply.title') }}</h2>
          <p>{{ t('apply.description') }}</p>
        </div>
        <div class="template-toolbar__actions">
          <div class="auto-sync-toggle">
            <div>
              <strong>{{ t('apply.autoSync') }}</strong>
              <span>
                {{
                  topologyBlocked
                    ? t('apply.topologyBlockedStatus')
                    : syncStatus.auto_sync
                      ? t('apply.autoSyncEnabled')
                      : t('apply.autoSyncDisabled')
                }}
              </span>
            </div>
            <el-switch
              :model-value="syncStatus.auto_sync"
              :disabled="topologyBlocked"
              :loading="autoSyncSaving"
              @change="toggleAutoSync"
            />
          </div>
          <el-button type="primary" :icon="Refresh" :loading="syncingNode" :disabled="topologyBlocked" @click="syncNode">
            {{ t('apply.syncConfig') }}
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="topologyBlocked"
        type="error"
        :title="t('apply.topologyBlockedTitle')"
        :description="t('apply.topologyBlockedDescription')"
        :closable="false"
        class="apply-topology-alert"
      >
        <template #default>
          <ul class="apply-topology-alert__list">
            <li v-for="item in topologyMessages" :key="item">{{ meshText(item) }}</li>
          </ul>
        </template>
      </el-alert>

      <div class="apply-panels">
        <el-card shadow="never" class="apply-panel">
          <template #header>
            <div class="apply-panel__header">
              <div class="apply-panel__title">
                <el-icon><Document /></el-icon>
                <div>
                  <strong>{{ t('apply.systemState') }}</strong>
                  <span>{{ t('apply.systemStateDescription') }}</span>
                </div>
              </div>
              <el-tag type="info" effect="plain">{{ t('apply.readOnly') }}</el-tag>
            </div>
          </template>
          <div class="config-code-shell">
            <el-scrollbar max-height="560px">
              <pre class="config-code-block">{{ previewContent }}</pre>
            </el-scrollbar>
          </div>
        </el-card>

        <el-card shadow="never" class="apply-panel">
          <template #header>
            <div class="apply-panel__header">
              <div class="apply-panel__title">
                <el-icon><EditPen /></el-icon>
                <div>
                  <strong>{{ t('apply.stagedState') }}</strong>
                  <span>{{ t('apply.stagedStateDescription') }}</span>
                </div>
              </div>
              <el-button size="small" type="primary" :icon="Check" :loading="savingApplied" @click="saveApplied">{{ t('apply.saveChanges') }}</el-button>
            </div>
          </template>
          <div class="config-code-shell config-code-shell--editable">
            <el-input
              v-model="appliedState.content"
              type="textarea"
              :rows="24"
              resize="none"
              class="config-code-editor"
            />
          </div>
        </el-card>
      </div>
    </div>
  </section>
</template>

<style scoped>
.node-template { display: grid; gap: 20px; }
.view-feedback { color: var(--app-muted); }
.view-feedback--silent { min-height: 140px; color: transparent; }
.view-feedback--error { color: var(--app-danger-text); }
.template-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.template-toolbar h2 { margin: 0; color: var(--app-text); font-size: 22px; }
.template-toolbar p { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.template-toolbar__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.apply-topology-alert { margin-bottom: 16px; }
.apply-topology-alert__list { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 4px; }
.auto-sync-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-width: 248px;
  padding: 10px 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-interactive);
}
.auto-sync-toggle strong,
.auto-sync-toggle span { display: block; }
.auto-sync-toggle strong { color: var(--app-text); font-size: 13px; }
.auto-sync-toggle span { margin-top: 4px; color: var(--app-muted); font-size: 12px; line-height: 1.4; }
.apply-panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.apply-panel { min-width: 0; border-color: var(--app-border-soft); background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%); }
.apply-panel :deep(.el-card__header) { padding: 16px 18px; border-bottom-color: var(--app-border-soft); }
.apply-panel :deep(.el-card__body) { padding: 18px; }
.apply-panel__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.apply-panel__title { display: flex; align-items: center; gap: 12px; color: var(--app-text-strong); }
.apply-panel__title .el-icon { color: var(--app-primary); font-size: 18px; }
.apply-panel__title strong { display: block; color: var(--app-text-strong); font-size: 16px; line-height: 1.2; }
.apply-panel__title span { display: block; margin-top: 4px; color: var(--app-muted); font-size: 13px; line-height: 1.4; }
.config-code-shell {
  overflow: hidden;
  min-height: 560px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(15, 139, 141, 0.04) 0%, rgba(15, 139, 141, 0) 56px),
    var(--app-surface-sunken);
}
.config-code-shell--editable {
  background:
    linear-gradient(180deg, rgba(15, 139, 141, 0.05) 0%, rgba(15, 139, 141, 0) 56px),
    var(--app-surface-elevated);
}
.config-code-shell :deep(.el-scrollbar__wrap) { padding: 18px; }
.config-code-block {
  margin: 0;
  color: var(--app-text-strong);
  font-size: 13px;
  line-height: 1.72;
  font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}
.config-code-editor :deep(.el-textarea__inner) {
  min-height: 560px !important;
  padding: 18px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  color: var(--app-text-strong);
  font-size: 13px;
  line-height: 1.72;
  font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
}
.config-code-editor :deep(.el-textarea__inner:focus) { box-shadow: none; }
@media (max-width: 1100px) { .apply-panels { grid-template-columns: 1fr; } }
@media (max-width: 860px) {
  .template-toolbar { flex-direction: column; align-items: stretch; }
  .auto-sync-toggle { width: 100%; }
}
</style>
