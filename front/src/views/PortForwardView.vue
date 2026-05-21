<script setup lang="ts">
import { ArrowLeft, Connection } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import PortForwardRuleForm from '@/components/tools/PortForwardRuleForm.vue'
import PortForwardRuleList from '@/components/tools/PortForwardRuleList.vue'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import type { ConfigRead, NodeRead, PortForwardRuleRead } from '@/types/api'
import { notify } from '@/utils/notify'

const router = useRouter()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const configs = shallowRef<ConfigRead[]>([])
const nodes = shallowRef<NodeRead[]>([])
const rules = shallowRef<PortForwardRuleRead[]>([])
const selectedConfigId = shallowRef('')
const createDialogVisible = shallowRef(false)
const loadError = shallowRef('')
const loading = shallowRef(false)
const changing = computed(() =>
  actions.isPending('create-port-forward').value
    || actions.isPending('delete-port-forward').value
    || actions.isPending('toggle-port-forward').value,
)
const selectedConfig = computed(() => configs.value.find((config) => config.id === selectedConfigId.value) || null)
const configNames = computed(() => Object.fromEntries(configs.value.map((config) => [config.id, config.name])))

function backToOtherTools() {
  void router.push('/tools/other')
}

async function loadConfigs() {
  loading.value = true
  loadError.value = ''
  try {
    configs.value = await api.configs()
    selectedConfigId.value = configs.value[0]?.id || ''
    await loadRules()
  } catch (error) {
    loadError.value = error instanceof ApiClientError ? error.message : t('tools.portForward.loadFailed')
  } finally {
    loading.value = false
  }
}

async function loadRuleNodes(configId: string) {
  if (!configId) {
    nodes.value = []
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    nodes.value = await api.nodes(configId)
  } catch (error) {
    loadError.value = error instanceof ApiClientError ? error.message : t('tools.portForward.loadFailed')
  } finally {
    loading.value = false
  }
}

async function loadRules() {
  if (!configs.value.length) {
    rules.value = []
    return
  }
  const grouped = await Promise.all(configs.value.map((config) => api.portForwardRules(config.id)))
  rules.value = grouped.flat().sort((left, right) => right.created_at.localeCompare(left.created_at))
}

function openCreateDialog() {
  createDialogVisible.value = true
  void loadRuleNodes(selectedConfigId.value)
}

async function createRule(payload: {
  from_node_id: string
  from_port: number
  to_node_id: string
  to_port: number
  to_platform: 'linux' | 'darwin'
  protocol: 'tcp' | 'udp' | 'all'
}) {
  if (!selectedConfig.value) return
  await actions.run('create-port-forward', async () => {
    try {
      await api.createPortForwardRule(selectedConfig.value!.id, payload)
      notify.success(t('tools.portForward.created'))
      createDialogVisible.value = false
      await loadRules()
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('tools.portForward.createFailed'))
    }
  })
}

async function removeRule(rule: PortForwardRuleRead) {
  try {
    await ElMessageBox.confirm(
      t('tools.portForward.deleteMessage', { name: rule.to_node.name, port: rule.to_port }),
      t('tools.portForward.deleteTitle'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
      },
    )
  } catch {
    return
  }
  await actions.run('delete-port-forward', async () => {
    try {
      await api.deletePortForwardRule(rule.id)
      notify.success(t('tools.portForward.deleted'))
      await loadRules()
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('tools.portForward.deleteFailed'))
    }
  })
}

async function toggleRule(rule: PortForwardRuleRead, enabled: boolean) {
  await actions.run('toggle-port-forward', async () => {
    try {
      await api.updatePortForwardRuleEnabled(rule.id, enabled)
      notify.success(t(enabled ? 'tools.portForward.enabledNotice' : 'tools.portForward.disabledNotice'))
      await loadRules()
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('tools.portForward.toggleFailed'))
    }
  })
}

watch(selectedConfigId, (configId) => {
  if (createDialogVisible.value) {
    void loadRuleNodes(configId)
  }
})

onMounted(() => {
  void loadConfigs()
})
</script>

<template>
  <section class="port-forward-page">
    <div class="tool-hero">
      <div class="tool-hero__copy">
        <el-button class="tool-hero__back" :icon="ArrowLeft" plain :disabled="changing" @click="backToOtherTools">{{ t('tools.portForward.back') }}</el-button>
        <div>
          <p class="tool-hero__eyebrow">{{ t('tools.other.title') }}</p>
          <h1>{{ t('tools.portForward.title') }}</h1>
          <p>{{ t('tools.portForward.description') }}</p>
        </div>
      </div>
      <el-icon><Connection /></el-icon>
    </div>

    <div v-if="loading && !configs.length" class="content-band view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError" class="content-band view-feedback view-feedback--error">{{ loadError }}</div>
    <template v-else>
      <PortForwardRuleList :rules="rules" :config-names="configNames" :disabled="changing" @create="openCreateDialog" @toggle="toggleRule" @remove="removeRule" />
    </template>

    <el-dialog v-model="createDialogVisible" class="port-forward-dialog" :title="t('tools.portForward.createTitle')" width="min(980px, calc(100vw - 32px))" :close-on-click-modal="!changing">
      <section class="port-forward-config">
        <div>
          <h2>{{ t('tools.portForward.configTitle') }}</h2>
          <p>{{ t('tools.portForward.configDescription') }}</p>
        </div>
        <el-select v-model="selectedConfigId" :placeholder="t('tools.portForward.noConfigs')" :disabled="changing || !configs.length">
          <el-option v-for="config in configs" :key="config.id" :label="config.name" :value="config.id" />
        </el-select>
      </section>
      <PortForwardRuleForm :nodes="nodes" :disabled="changing || !selectedConfig" @submit="createRule" />
    </el-dialog>
  </section>
</template>

<style scoped>
.port-forward-page { display: grid; gap: 18px; }
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
.port-forward-config {
  display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 18px 24px;
  border: 1px solid var(--app-border); border-radius: 14px; background: var(--app-surface); box-shadow: var(--app-shadow-sm);
}
:deep(.port-forward-dialog .el-dialog__body) { display: grid; gap: 14px; }
.port-forward-config div { min-width: 0; }
.port-forward-config h2,
.port-forward-config p { margin: 0; }
.port-forward-config h2 { color: var(--app-text-strong); letter-spacing: 0; }
.port-forward-config p { margin-top: 6px; color: var(--app-muted); line-height: 1.55; }
.port-forward-config .el-select { flex: 0 1 320px; width: 320px; max-width: 100%; }
.view-feedback { padding: 18px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-sunken); }
.view-feedback--error { border-color: var(--app-danger-border); color: var(--app-danger-text); }
@media (max-width: 720px) {
  .tool-hero { align-items: flex-start; padding: 24px; }
  .tool-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .port-forward-config { align-items: stretch; flex-direction: column; }
  .port-forward-config .el-select { flex-basis: auto; width: 100%; }
}
</style>
