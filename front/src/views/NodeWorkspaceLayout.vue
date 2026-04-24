<script setup lang="ts">
import { ArrowLeft, Delete, Key, Setting } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigRead, EndpointStatusRead, NodeRead, NodeWorkspaceUpdatedPayload, RealtimeEvent, TagRead } from '@/types/api'
import { notifyChangeHints } from '@/utils/changeHints'
import { requiredTextRule } from '@/utils/formRules'
import { normalizeTags, toNodeUpdatePayload } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const config = shallowRef<ConfigRead | null>(null)
const node = shallowRef<NodeRead | null>(null)
const configTags = shallowRef<TagRead[]>([])
const endpointStatus = shallowRef<EndpointStatusRead | null>(null)
const settingsVisible = shallowRef(false)
const settingsFormRef = shallowRef<FormInstance>()
const loading = shallowRef(false)
const loadError = shallowRef('')
let loadTicket = 0
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'node.workspace.updated') return
  const payload = event.payload as unknown as NodeWorkspaceUpdatedPayload
  if (payload.config_id !== String(route.params.configId) || payload.node_id !== String(route.params.nodeId)) return
  config.value = payload.workspace.config
  node.value = payload.workspace.node
  endpointStatus.value = payload.workspace.endpoint_status
  configTags.value = payload.workspace.tags
})

const settingsForm = reactive({
  name: '',
  ipv4_address: '',
  ipv6_address: '',
  listen_port: null as number | null,
  virtual_ip: '',
  mtu: null as number | null,
  dns: '',
  auto_sync: true,
  node_type: 'dynamic' as NodeRead['node_type'],
  public_key: '',
  private_key: '',
  tags: [] as string[],
})
const settingsRules: FormRules<typeof settingsForm> = {
  name: [requiredTextRule('fields.name')],
  virtual_ip: [requiredTextRule('fields.virtualIp')],
}

const tabs = computed(() => {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  const isStaticNode = node.value?.node_type === 'static'
  const mqttDisabled = endpointStatus.value?.mqtt_service.enabled === false
  return [
    { label: t('nodeWorkspace.mesh'), path: `/configs/${configId}/nodes/${nodeId}/mesh`, align: 'left' as const },
    { label: t('nodeWorkspace.apply'), path: `/configs/${configId}/nodes/${nodeId}/apply`, align: 'left' as const },
    {
      label: t('nodeWorkspace.control'),
      path: `/configs/${configId}/nodes/${nodeId}/control`,
      align: 'left' as const,
      disabled: isStaticNode || mqttDisabled,
    },
    { label: t('nodeWorkspace.download'), path: `/configs/${configId}/nodes/${nodeId}/download`, align: 'right' as const },
  ]
})
const primaryTabs = computed(() => tabs.value.filter((item) => item.align === 'left'))
const actionTabs = computed(() => tabs.value.filter((item) => item.align === 'right'))

const allTags = computed(() => configTags.value.map((item) => item.name))

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? t('nodeWorkspace.staticNode') : t('nodeWorkspace.dynamicNode')
}

async function load() {
  const ticket = ++loadTicket
  loading.value = true
  loadError.value = ''
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  try {
    const [configs, nextNode, nextStatus, nextTags] = await Promise.all([
      api.configs(),
      api.node(nodeId),
      api.endpointStatus(configId, nodeId),
      api.tags(configId),
    ])
    if (ticket !== loadTicket) return
    config.value = configs.find((item) => item.id === configId) ?? null
    node.value = nextNode
    endpointStatus.value = nextStatus
    configTags.value = nextTags
  } catch (error) {
    if (ticket !== loadTicket) return
    loadError.value = error instanceof ApiClientError ? error.message : t('nodeWorkspace.loadFailed')
    throw error
  } finally {
    if (ticket === loadTicket) loading.value = false
  }
}

function goBack() {
  void router.push(`/configs/${route.params.configId}`)
}

function fillSettingsForm() {
  if (!node.value) return
  Object.assign(settingsForm, {
    name: node.value.name,
    ipv4_address: node.value.ipv4_address || '',
    ipv6_address: node.value.ipv6_address || '',
    listen_port: node.value.listen_port,
    virtual_ip: node.value.virtual_ip || '',
    mtu: node.value.mtu,
    dns: node.value.dns || '',
    auto_sync: node.value.auto_sync,
    node_type: node.value.node_type,
    public_key: node.value.public_key,
    private_key: node.value.private_key,
    tags: [...node.value.tags],
  })
}

function openSettings() {
  fillSettingsForm()
  settingsVisible.value = true
}

function handleTabClick(disabled: boolean) {
  if (!disabled) return
  if (node.value?.node_type === 'static') {
    notify.info(t('nodeWorkspace.staticControlUnavailable'))
    return
  }
  notify.info(t('nodeWorkspace.mqttControlUnavailable'))
}

async function autofillKeys() {
  try {
    const keys = await api.generateKeys()
    settingsForm.private_key = keys.private_key
    settingsForm.public_key = keys.public_key
    notify.success(t('nodeWorkspace.keyGenerated'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('nodeWorkspace.keyGenerateFailed'))
  }
}

async function saveNodeSettings() {
  if (!node.value) return
  const valid = await settingsFormRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    const result = await api.updateNode(node.value.id, toNodeUpdatePayload(node.value, {
      name: settingsForm.name,
      ipv4_address: settingsForm.ipv4_address || null,
      ipv6_address: settingsForm.ipv6_address || null,
      listen_port: settingsForm.listen_port,
      virtual_ip: settingsForm.virtual_ip || null,
      mtu: settingsForm.mtu,
      dns: settingsForm.dns || null,
      auto_sync: settingsForm.auto_sync,
      node_type: settingsForm.node_type,
      public_key: settingsForm.public_key,
      private_key: settingsForm.private_key,
      tags: normalizeTags(settingsForm.tags),
    }))
    settingsVisible.value = false
    await load()
    notify.success(t('nodeWorkspace.settingsSaved'))
    notifyChangeHints(result.change_hints)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('nodeWorkspace.settingsSaveFailed'))
  }
}

async function deleteNodeFromSettings() {
  if (!node.value) return
  try {
    await ElMessageBox.confirm(
      t('nodeWorkspace.deleteConfirmText', { name: node.value.name }),
      t('nodeWorkspace.deleteConfirmTitle'),
      {
        type: 'warning',
        confirmButtonText: t('nodeWorkspace.deleteEndpoint'),
        cancelButtonText: t('common.cancel'),
        confirmButtonClass: 'el-button--danger',
      },
    )
    const configId = node.value.config_id
    await api.deleteNode(node.value.id)
    settingsVisible.value = false
    notify.success(t('nodeWorkspace.deleted'))
    await router.push(`/configs/${configId}`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    notify.error(error instanceof ApiClientError ? error.message : t('nodeWorkspace.deleteFailed'))
  }
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    try {
      await load()
    } catch {
      notify.error(loadError.value || t('nodeWorkspace.loadFailed'))
    }
  },
)

onMounted(async () => {
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('nodeWorkspace.loadFailed'))
  }
})
</script>

<template>
  <div class="node-workspace">
    <div class="node-header-card">
      <div class="node-header-card__top">
        <el-button :icon="ArrowLeft" @click="goBack">{{ t('nodeWorkspace.backToConfig') }}</el-button>
        <div class="node-header-card__actions">
          <span class="node-header-card__config">{{ config?.name || t('nodeWorkspace.localConfig') }}</span>
          <el-button v-if="node" type="primary" plain :icon="Setting" @click="openSettings">{{ t('nodeWorkspace.endpointSettings') }}</el-button>
        </div>
      </div>

      <div v-if="node" class="node-header-card__main">
        <div>
          <h1>{{ node.name }}</h1>
          <div class="node-header-card__tags">
            <el-tag type="info">{{ nodeTypeLabel(node.node_type) }}</el-tag>
            <el-tag v-if="node.node_type === 'dynamic'" :type="endpointStatus?.runtime.online ? 'success' : 'info'">
              {{ endpointStatus?.runtime.online ? t('nodeWorkspace.online') : t('nodeWorkspace.offline') }}
            </el-tag>
            <el-tag v-for="tag in node.tags" :key="tag" type="info">{{ tag }}</el-tag>
          </div>
        </div>
      </div>

      <div v-if="node" class="node-props-grid">
        <div class="node-prop-item">
          <span class="node-prop-label">{{ t('nodeWorkspace.virtualIp') }}</span>
          <span class="node-prop-value">{{ node.virtual_ip || t('nodeWorkspace.unset') }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">{{ t('nodeWorkspace.publicIpv4') }}</span>
          <span class="node-prop-value">{{ node.ipv4_address || t('nodeWorkspace.unset') }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">{{ t('nodeWorkspace.publicIpv6') }}</span>
          <span class="node-prop-value">{{ node.ipv6_address || t('nodeWorkspace.unset') }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">{{ t('nodeWorkspace.peerCount') }}</span>
          <span class="node-prop-value">{{ endpointStatus?.runtime.peers_total ?? 0 }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">{{ t('nodeWorkspace.wgState') }}</span>
          <span class="node-prop-value">{{ endpointStatus?.runtime.wg_runtime_state || 'unknown' }}</span>
        </div>
      </div>

      <div class="node-tabs">
        <div class="node-tabs__group">
        <RouterLink
          v-for="tab in primaryTabs"
          :key="tab.path"
          :to="tab.disabled ? route.fullPath : tab.path"
          class="node-tab"
          :class="{
            'node-tab--active': route.path === tab.path,
            'node-tab--disabled': tab.disabled,
          }"
          :aria-disabled="tab.disabled ? 'true' : 'false'"
          @click.prevent="handleTabClick(Boolean(tab.disabled))"
        >
          {{ tab.label }}
        </RouterLink>
        </div>
        <div class="node-tabs__group node-tabs__group--right">
          <RouterLink
            v-for="tab in actionTabs"
            :key="tab.path"
            :to="tab.path"
            class="node-tab node-tab--action"
            :class="{ 'node-tab--active': route.path === tab.path }"
          >
            {{ tab.label }}
          </RouterLink>
        </div>
      </div>
    </div>

    <RouterView v-slot="{ Component, route: viewRoute }">
      <Transition name="route-template" appear>
        <component :is="Component" :key="viewRoute.fullPath" />
      </Transition>
    </RouterView>

    <div v-if="loading && !node" class="view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !node" class="view-feedback view-feedback--error">{{ loadError }}</div>

    <el-dialog v-model="settingsVisible" :title="t('nodeWorkspace.endpointSettings')" width="640px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Setting /></el-icon></span>
        <div>
          <h3>{{ t('nodeWorkspace.settingsHeading') }}</h3>
          <p>{{ t('nodeWorkspace.settingsDescription') }}</p>
        </div>
      </div>

      <el-form ref="settingsFormRef" :model="settingsForm" :rules="settingsRules" class="dialog-form" label-position="top">
        <el-form-item :label="t('nodeWorkspace.name')" prop="name" required>
          <el-input v-model="settingsForm.name" />
        </el-form-item>
        <el-form-item :label="t('nodeWorkspace.type')">
          <el-segmented
            v-model="settingsForm.node_type"
            :options="[
              { label: t('nodeWorkspace.dynamicNode'), value: 'dynamic' },
              { label: t('nodeWorkspace.staticNode'), value: 'static' },
            ]"
          />
        </el-form-item>
        <div class="form-grid">
          <el-form-item :label="t('nodeWorkspace.publicIpv4')">
            <el-input v-model="settingsForm.ipv4_address" :placeholder="t('nodeWorkspace.ipOrDomain')" />
          </el-form-item>
          <el-form-item :label="t('nodeWorkspace.publicIpv6')">
            <el-input v-model="settingsForm.ipv6_address" :placeholder="t('nodeWorkspace.ipOrDomain')" />
          </el-form-item>
          <el-form-item :label="t('nodeWorkspace.listenPort')">
            <el-input-number v-model="settingsForm.listen_port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('nodeWorkspace.virtualIp')" prop="virtual_ip" required>
            <el-input v-model="settingsForm.virtual_ip" />
          </el-form-item>
          <el-form-item label="MTU">
            <el-input-number v-model="settingsForm.mtu" :min="576" :max="65535" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item label="DNS">
          <el-input v-model="settingsForm.dns" />
        </el-form-item>
        <el-form-item :label="t('nodeWorkspace.tags')">
          <el-select
            v-model="settingsForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            :placeholder="t('nodeWorkspace.selectOrInputTag')"
            style="width: 100%"
          >
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
        <div class="switch-row">
          <div>
            <strong>{{ t('nodeWorkspace.autoSync') }}</strong>
            <span>{{ t('nodeWorkspace.autoSyncDescription') }}</span>
          </div>
          <el-switch v-model="settingsForm.auto_sync" />
        </div>
        <el-form-item :label="t('nodeWorkspace.privateKey')">
          <el-input v-model="settingsForm.private_key" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('nodeWorkspace.publicKey')">
          <el-input v-model="settingsForm.public_key" type="textarea" :rows="3" />
        </el-form-item>
        <el-button plain :icon="Key" @click="autofillKeys">{{ t('nodeWorkspace.generateKeys') }}</el-button>
      </el-form>

      <template #footer>
        <el-button type="danger" plain :icon="Delete" @click="deleteNodeFromSettings">{{ t('nodeWorkspace.deleteEndpoint') }}</el-button>
        <el-button @click="settingsVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveNodeSettings">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.node-workspace { display: grid; gap: 20px; }
.node-header-card { padding: 22px; border: 1px solid var(--app-border); border-radius: 8px; background: linear-gradient(180deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%); box-shadow: var(--app-shadow-md); }
.node-header-card__top { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.node-header-card__actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 10px; }
.node-header-card__config { color: var(--app-muted); font-weight: 650; }
.node-header-card__main { display: flex; justify-content: space-between; gap: 16px; margin-top: 18px; }
.node-header-card__main h1 { margin: 0; color: var(--app-text); font-size: 30px; line-height: 1.2; }
.node-header-card__tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.node-props-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.node-prop-item { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); box-shadow: inset 0 1px 0 color-mix(in srgb, white 22%, transparent); }
.node-prop-label { color: var(--app-faint); font-size: 12px; font-weight: 650; }
.node-prop-value { color: var(--app-text-strong); font-weight: 750; word-break: break-word; }
.node-tabs { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--app-border-soft); }
.node-tabs__group { display: flex; flex-wrap: wrap; gap: 10px; }
.node-tabs__group--right { justify-content: flex-end; }
.node-tab { min-height: 40px; padding: 10px 16px; border: 1px solid var(--app-border); border-radius: 8px; color: color-mix(in srgb, var(--app-text) 72%, var(--app-muted)); background: var(--app-surface); text-decoration: none; font-weight: 700; transition: transform 160ms ease, border-color 160ms ease, background-color 160ms ease, box-shadow 160ms ease; }
.node-tab--action { border-color: var(--app-border-accent); background: var(--app-surface-interactive); color: color-mix(in srgb, var(--app-text) 84%, var(--app-primary)); }
.node-tab:hover { transform: translateY(-1px); border-color: var(--app-border-accent); background: var(--app-surface-interactive); box-shadow: var(--app-shadow-sm); }
.node-tab--disabled,
.node-tab--disabled:hover { transform: none; border-color: var(--app-border-soft); background: var(--app-surface-sunken); color: var(--app-faint); box-shadow: none; cursor: not-allowed; }
.node-tab:focus-visible { outline: 0; box-shadow: var(--app-focus); }
.node-tab--active { color: var(--app-primary-strong); border-color: var(--app-primary); background: var(--app-surface-selected); }
.node-tab--disabled.node-tab--active { color: var(--app-faint); border-color: var(--app-border-soft); background: var(--app-surface-sunken); }
.view-feedback { padding: 18px 20px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-sunken); color: color-mix(in srgb, var(--app-text) 68%, var(--app-muted)); box-shadow: var(--app-shadow-sm); }
.view-feedback--silent { min-height: 88px; background: transparent; border-color: transparent; box-shadow: none; }
.view-feedback--error { border-color: var(--app-danger-border); background: var(--app-danger-soft); color: var(--app-danger-text); }
.dialog-intro { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); }
.dialog-intro__icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 42px; height: 42px; border: 1px solid var(--app-border-accent); border-radius: 8px; background: var(--app-primary-soft); color: var(--app-primary); }
.dialog-intro h3 { margin: 0; color: var(--app-text); }
.dialog-intro p { margin: 5px 0 0; color: var(--app-muted); line-height: 1.5; }
.dialog-form { display: grid; gap: 2px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-elevated); }
.switch-row strong, .switch-row span { display: block; }
.switch-row strong { color: var(--app-text); }
.switch-row span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
@media (max-width: 1100px) { .node-props-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) {
  .node-header-card__top, .node-header-card__main, .switch-row, .node-tabs { flex-direction: column; align-items: stretch; }
  .node-header-card__actions { justify-content: flex-start; }
  .node-props-grid, .form-grid { grid-template-columns: 1fr; }
  .node-tabs__group--right { justify-content: flex-start; }
}
</style>
