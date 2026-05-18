<script setup lang="ts">
import { ArrowLeft, Files, Plus, Setting } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import { useHomePrefs } from '@/composables/useHomePrefs'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigListUpdatedPayload, ConfigRead, RealtimeEvent } from '@/types/api'
import { cidrRule, requiredTextRule } from '@/utils/formRules'
import { notify } from '@/utils/notify'
import ConfigProtocolForm from '@/components/config/ConfigProtocolForm.vue'
import type { ConfigProtocolModel } from '@/components/config/ConfigProtocolForm.vue'

const router = useRouter()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const creatingConfig = actions.isPending('create-config')
const { statusFilter, sortKey, layoutMode } = useHomePrefs()

const configs = shallowRef<ConfigRead[]>([])
let lastRealtimeVersion = 0
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'config.list.updated') {
    configs.value = (event.payload as unknown as ConfigListUpdatedPayload).configs
  }
})
const dialogVisible = shallowRef(false)
const dialogAdvanced = shallowRef(false)
const formRef = shallowRef<FormInstance>()
const form = reactive({
  name: '',
  description: '',
  enabled: true,
  virtual_subnet: '10.66.0.0/24',
  default_listen_port: 51820,
  default_mtu: 1420,
  default_dns: '1.1.1.1',
  auto_sync: true,
  tunnel_protocol: 'wireguard',
  awg_s1: null,
  awg_s2: null,
  awg_s3: null,
  awg_s4: null,
  awg_h1: null,
  awg_h2: null,
  awg_h3: null,
  awg_h4: null,
} satisfies ConfigProtocolModel & {
  name: string
  description: string
  enabled: boolean
  virtual_subnet: string
  default_listen_port: number
  default_mtu: number | null
  default_dns: string | null
  auto_sync: boolean
})
const protocolForm = computed<ConfigProtocolModel>({
  get: () => form,
  set: (next) => Object.assign(form, next),
})
const formRules: FormRules<typeof form> = {
  name: [requiredTextRule('fields.name')],
  virtual_subnet: [cidrRule('home.virtualSubnetField')],
}

const onlineNodeTotal = computed(() => configs.value.reduce((sum, config) => sum + config.online_node_count, 0))

const portalMetrics = computed(() => [
  { label: t('home.metricConfigs'), value: configs.value.length },
  { label: t('home.metricNodes'), value: configs.value.reduce((sum, config) => sum + config.node_count, 0) },
  { label: t('home.metricDynamicNodes'), value: configs.value.reduce((sum, config) => sum + config.dynamic_node_count, 0) },
])

const statusFilterOptions = computed(() => [
  { label: t('home.statusAll'), value: 'all' },
  { label: t('home.enabled'), value: 'enabled' },
  { label: t('home.disabled'), value: 'disabled' },
])

const sortOptions = computed(() => [
  { label: t('home.sortUpdated'), value: 'updated' },
  { label: t('home.sortName'), value: 'name' },
  { label: t('home.sortNodes'), value: 'nodes' },
  { label: t('home.sortOnline'), value: 'online' },
])

const layoutOptions = computed(() => [
  { label: t('home.layoutGrid'), value: 'grid' },
  { label: t('home.layoutList'), value: 'list' },
])

const visibleConfigs = computed(() => {
  const items = configs.value.filter((config) => {
    if (statusFilter.value === 'enabled') return config.enabled
    if (statusFilter.value === 'disabled') return !config.enabled
    return true
  })
  return [...items].sort((left, right) => {
    if (sortKey.value === 'name') return left.name.localeCompare(right.name)
    if (sortKey.value === 'nodes') return right.node_count - left.node_count || left.name.localeCompare(right.name)
    if (sortKey.value === 'online') return right.online_node_count - left.online_node_count || left.name.localeCompare(right.name)
    return right.updated_at.localeCompare(left.updated_at)
  })
})

function configStats(config: ConfigRead) {
  return [
    { label: t('home.virtualSubnet'), value: config.virtual_subnet },
    { label: t('home.nodeCount'), value: config.node_count },
    { label: t('home.onlineNodeCount'), value: config.online_node_count },
    { label: t('home.dynamicNodeCount'), value: config.dynamic_node_count },
  ]
}

function formatHomeDate(value: string) {
  if (!value) return t('common.unknown')
  return value.replace('T', ' ').slice(0, 16)
}

async function load() {
  configs.value = await api.configs()
}

async function submit() {
  await actions.run('create-config', async () => {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return
    try {
      const config = await api.createConfig(form)
      dialogVisible.value = false
      await load()
      await router.push(`/configs/${config.id}`)
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('home.createFailed'))
    }
  })
}

function openCreateDialog() {
  dialogAdvanced.value = false
  dialogVisible.value = true
}

async function openConfig(configId: string) {
  await router.push(`/configs/${configId}`)
}

onMounted(async () => {
  try {
    await load()
    realtime.connect()
    lastRealtimeVersion = realtime.connectionVersion.value
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('home.loadFailed'))
  }
})

watch(
  () => realtime.connectionVersion.value,
  async (nextVersion) => {
    if (nextVersion <= 0) return
    if (lastRealtimeVersion === 0) {
      lastRealtimeVersion = nextVersion
      return
    }
    lastRealtimeVersion = nextVersion
    try {
      await load()
    } catch {
      // Keep reconnect reconciliation silent.
    }
  },
)
</script>

<template>
  <section class="home-portal">
    <div class="home-portal__copy">
      <span class="home-portal__eyebrow">{{ t('home.eyebrow') }}</span>
      <div class="home-portal__headline">
        <img class="home-portal__logo" src="/logo.png" alt="WG Free Mesh" />
        <div class="home-portal__headline-copy">
          <h1>{{ t('home.title') }}</h1>
          <p>{{ t('home.description') }}</p>
        </div>
      </div>
      <div class="home-portal__flow" aria-hidden="true">
        <span>
          <i></i>
          {{ t('home.portalStageConfig') }}
        </span>
        <span>
          <i></i>
          {{ t('home.portalStageMqtt') }}
        </span>
        <span>
          <i></i>
          {{ t('home.portalStageClient') }}
        </span>
      </div>
    </div>

    <div class="home-portal__panel">
      <div class="home-portal__primary-metric">
        <span>{{ t('home.metricOnlineNodes') }}</span>
        <strong>{{ onlineNodeTotal }}</strong>
      </div>
      <div class="home-portal__metrics">
        <div v-for="metric in portalMetrics" :key="metric.label" class="home-portal__metric">
          <strong>{{ metric.value }}</strong>
          <span>{{ metric.label }}</span>
        </div>
      </div>
    </div>
  </section>

  <section class="config-toolbar">
    <div>
      <h2>{{ t('home.configSectionTitle') }}</h2>
    </div>
    <div class="config-toolbar__actions">
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">{{ t('home.createConfig') }}</el-button>
      <el-segmented v-model="statusFilter" :options="statusFilterOptions" :aria-label="t('home.statusFilter')" />
      <el-select v-model="sortKey" class="config-sort-select" :aria-label="t('home.sortLabel')">
        <el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-segmented v-model="layoutMode" :options="layoutOptions" :aria-label="t('home.layoutLabel')" />
    </div>
  </section>

  <section v-if="layoutMode === 'grid'" class="config-grid">
    <button
      v-for="config in visibleConfigs"
      :key="config.id"
      class="config-card"
      :class="{ 'config-card--danger': config.topology_invalid }"
      @click="openConfig(config.id)"
    >
      <div class="config-card__head">
        <span class="config-card__icon">
          <el-icon><Files /></el-icon>
        </span>
        <div class="config-card__status-tags">
          <el-tag v-if="config.topology_invalid" type="danger">{{ t('configOverview.topologyFailed') }}</el-tag>
          <el-tag :type="config.enabled ? 'success' : 'info'">{{ config.enabled ? t('home.enabled') : t('home.disabled') }}</el-tag>
        </div>
      </div>

      <div class="config-card__body">
        <h3>{{ config.name }}</h3>
        <p>{{ config.description || t('home.noDescription') }}</p>
      </div>

      <dl class="config-stat-grid">
        <div v-for="stat in configStats(config)" :key="stat.label">
          <dt>{{ stat.label }}</dt>
          <dd>{{ stat.value }}</dd>
        </div>
      </dl>

      <div class="config-card__foot">
        <el-tag v-if="config.topology_invalid" type="danger">{{ t('home.topologyErrorCount', { count: config.topology_error_count }) }}</el-tag>
        <span v-else></span>
        <span>{{ formatHomeDate(config.updated_at) }}</span>
      </div>
    </button>
  </section>

  <section v-else class="config-list">
    <button
      v-for="config in visibleConfigs"
      :key="config.id"
      class="config-list-row"
      :class="{ 'config-list-row--danger': config.topology_invalid }"
      @click="openConfig(config.id)"
    >
      <div class="config-list-row__main">
        <span class="config-card__icon">
          <el-icon><Files /></el-icon>
        </span>
        <div>
          <div class="config-list-row__title">
            <h3>{{ config.name }}</h3>
            <div class="config-card__status-tags">
              <el-tag v-if="config.topology_invalid" type="danger">{{ t('configOverview.topologyFailed') }}</el-tag>
              <el-tag :type="config.enabled ? 'success' : 'info'">{{ config.enabled ? t('home.enabled') : t('home.disabled') }}</el-tag>
            </div>
          </div>
          <p>{{ config.description || t('home.noDescription') }}</p>
        </div>
      </div>

      <dl class="config-stat-grid config-stat-grid--list">
        <div v-for="stat in configStats(config)" :key="stat.label">
          <dt>{{ stat.label }}</dt>
          <dd>{{ stat.value }}</dd>
        </div>
      </dl>

      <div class="config-card__foot">
        <el-tag v-if="config.topology_invalid" type="danger">{{ t('home.topologyErrorCount', { count: config.topology_error_count }) }}</el-tag>
        <span v-else></span>
        <span>{{ formatHomeDate(config.updated_at) }}</span>
      </div>
    </button>
  </section>

  <section v-if="!visibleConfigs.length" class="config-empty">
    <span class="config-empty__icon">
      <el-icon><Files /></el-icon>
    </span>
    <strong>{{ configs.length ? t('home.noMatchingConfigs') : t('home.emptyTitle') }}</strong>
    <span v-if="!configs.length">{{ t('home.emptyDescription') }}</span>
    <el-button type="primary" :icon="Plus" @click="openCreateDialog">{{ t('home.createConfig') }}</el-button>
  </section>

  <el-dialog v-model="dialogVisible" :title="t('home.dialogTitle')" width="620px">
    <div class="dialog-top-actions">
      <el-button v-if="dialogAdvanced" :icon="ArrowLeft" @click="dialogAdvanced = false">{{ t('common.back') }}</el-button>
      <el-button v-else :icon="Setting" @click="dialogAdvanced = true">{{ t('protocol.advancedSettings') }}</el-button>
    </div>
    <template v-if="!dialogAdvanced">
    <div class="dialog-intro">
      <span class="dialog-intro__icon">
        <el-icon><Files /></el-icon>
      </span>
      <div>
        <h3>{{ t('home.dialogHeading') }}</h3>
        <p>{{ t('home.dialogDescription') }}</p>
      </div>
    </div>

    <el-form ref="formRef" :model="form" :rules="formRules" class="dialog-form" label-position="top">
      <el-form-item :label="t('fields.name')" prop="name" required>
        <el-input v-model="form.name" :placeholder="t('home.exampleName')" />
      </el-form-item>
      <el-form-item :label="t('home.descriptionField')">
        <el-input v-model="form.description" type="textarea" :rows="3" :placeholder="t('home.descriptionPlaceholder')" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item :label="t('home.virtualSubnetField')" prop="virtual_subnet" required>
          <el-input v-model="form.virtual_subnet" />
        </el-form-item>
        <el-form-item :label="t('home.defaultListenPort')">
          <el-input-number v-model="form.default_listen_port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('home.defaultMtu')">
          <el-input-number v-model="form.default_mtu" :min="576" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('home.defaultDns')">
          <el-input v-model="form.default_dns" />
        </el-form-item>
      </div>
      <div class="switch-row">
        <div>
          <strong>{{ t('home.autoSync') }}</strong>
          <span>{{ t('home.autoSyncDescription') }}</span>
        </div>
        <el-switch v-model="form.auto_sync" />
      </div>
    </el-form>
    </template>
    <ConfigProtocolForm v-else v-model="protocolForm" />

    <template #footer>
      <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :icon="Plus" :loading="creatingConfig" @click="submit">{{ t('home.create') }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.home-portal {
  position: relative;
  display: grid;
  grid-template-columns: minmax(420px, 1.35fr) minmax(280px, 0.65fr);
  gap: 28px;
  min-height: 260px;
  padding: 34px;
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background:
    radial-gradient(circle at 82% 12%, color-mix(in srgb, var(--el-color-success) 18%, transparent), transparent 32%),
    linear-gradient(124deg, color-mix(in srgb, var(--app-primary) 13%, transparent), transparent 46%),
    linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-md);
}

.home-portal::before {
  content: "";
  position: absolute;
  inset: auto -12% -42% 34%;
  width: 68%;
  height: 74%;
  pointer-events: none;
  border: 1px solid color-mix(in srgb, var(--app-border-accent) 58%, transparent);
  border-radius: 999px;
  opacity: 0.26;
}

.home-portal::after {
  content: "";
  position: absolute;
  inset: 18px;
  pointer-events: none;
  border: 1px solid color-mix(in srgb, var(--app-border-soft) 74%, transparent);
  border-radius: 8px;
}

.home-portal__copy,
.home-portal__panel {
  position: relative;
  z-index: 1;
}

.home-portal__copy {
  display: grid;
  align-content: space-between;
  gap: 28px;
  min-width: 0;
}

.home-portal__eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.home-portal__headline {
  display: grid;
  grid-template-columns: 142px minmax(0, 1fr);
  align-items: center;
  gap: 26px;
  min-width: 0;
}

.home-portal__logo {
  width: 142px;
  height: 142px;
  border-radius: 8px;
  object-fit: contain;
  filter: drop-shadow(0 18px 28px color-mix(in srgb, var(--app-primary) 28%, transparent));
}

.home-portal__headline-copy {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.home-portal__headline-copy h1 {
  margin: 0;
  color: var(--app-text-strong);
  font-size: 46px;
  line-height: 1.05;
}

.home-portal p {
  margin: 0;
  color: var(--app-muted);
  max-width: 560px;
  font-size: 15px;
  line-height: 1.6;
}

.home-portal__flow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  align-self: end;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--app-border-soft) 78%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--app-overlay) 68%, transparent);
}

.home-portal__flow span {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  padding: 0 12px;
  color: var(--app-text-strong);
  font-size: 12px;
  font-weight: 800;
}

.home-portal__flow span:not(:last-child)::after {
  content: "";
  position: absolute;
  right: 0;
  width: 1px;
  height: 18px;
  background: var(--app-border-soft);
}

.home-portal__flow span:not(:last-child)::before {
  content: "";
  position: absolute;
  left: 33px;
  right: 12px;
  top: 50%;
  height: 1px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--app-primary) 42%, transparent), transparent);
}

.home-portal__flow i {
  position: relative;
  z-index: 1;
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border: 2px solid var(--app-primary);
  border-radius: 999px;
  background: var(--app-surface-elevated);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--app-primary) 12%, transparent);
}

.home-portal__panel {
  display: grid;
  gap: 12px;
  align-content: end;
}

.home-portal__primary-metric {
  display: grid;
  gap: 6px;
  min-height: 132px;
  padding: 20px;
  border: 1px solid color-mix(in srgb, var(--app-border-accent) 52%, transparent);
  border-radius: 8px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-primary) 12%, transparent), transparent 68%),
    color-mix(in srgb, var(--app-overlay-strong) 90%, transparent);
  box-shadow: var(--app-shadow-sm);
}

.home-portal__primary-metric span {
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 700;
}

.home-portal__primary-metric strong {
  color: var(--app-text-strong);
  font-size: 58px;
  line-height: 1;
}

.home-portal__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.home-portal__metric {
  display: grid;
  gap: 3px;
  min-height: 72px;
  padding: 12px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: color-mix(in srgb, var(--app-overlay) 84%, transparent);
}

.home-portal__metric strong {
  color: var(--app-text-strong);
  font-size: 28px;
  line-height: 1;
}

.home-portal__metric span {
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 650;
}

.config-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 20px;
  padding: 14px 16px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-elevated);
  box-shadow: var(--app-shadow-sm);
}

.config-toolbar h2 {
  margin: 0;
}

.config-toolbar h2 {
  color: var(--app-text);
  font-size: 20px;
}

.config-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.config-sort-select {
  width: 150px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 380px), 1fr));
  gap: 16px;
  margin-top: 16px;
}

.config-card {
  display: grid;
  gap: 18px;
  width: 100%;
  min-width: 0;
  min-height: 292px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-sm);
  cursor: pointer;
  text-align: left;
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.config-card--danger {
  border-color: var(--app-danger-border);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-danger-border) 24%, transparent), var(--app-shadow-sm);
}

.config-card:hover {
  transform: translateY(-3px);
  border-color: var(--app-border-accent);
  box-shadow: var(--app-shadow-md);
}

.config-card--danger:hover {
  border-color: color-mix(in srgb, var(--app-danger-border) 80%, var(--app-primary));
}

.config-card:focus-visible {
  outline: 0;
  box-shadow: var(--app-focus), var(--app-shadow-md);
}

.config-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.config-card__status-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.config-card__icon,
.config-empty__icon,
.dialog-intro__icon {
  display: inline-grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--app-border-accent);
  border-radius: 8px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
}

.config-card__body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.config-card__body h3 {
  overflow: hidden;
  margin: 0;
  color: var(--app-text-strong);
  font-size: 20px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-card__body p {
  display: -webkit-box;
  overflow: hidden;
  margin: 0;
  color: var(--app-muted);
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.config-stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.config-stat-grid div {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}

.config-stat-grid dt {
  color: var(--app-faint);
  font-size: 12px;
}

.config-stat-grid dd {
  overflow: hidden;
  margin: 6px 0 0;
  color: var(--app-text);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  color: var(--app-faint);
  font-size: 12px;
  font-weight: 650;
}

.config-card__foot > span:last-child {
  overflow: hidden;
  min-width: 0;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.config-list-row {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) minmax(560px, 5fr);
  gap: 18px;
  align-items: center;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-sm);
  cursor: pointer;
  text-align: left;
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.config-list-row:hover {
  transform: translateY(-2px);
  border-color: var(--app-border-accent);
  box-shadow: var(--app-shadow-md);
}

.config-list-row--danger {
  border-color: var(--app-danger-border);
}

.config-list-row__main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.config-list-row__main > div {
  min-width: 0;
}

.config-list-row__title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.config-list-row__title h3 {
  overflow: hidden;
  margin: 0;
  color: var(--app-text-strong);
  font-size: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-list-row p {
  display: -webkit-box;
  margin: 8px 0 0;
  overflow: hidden;
  color: var(--app-muted);
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.config-stat-grid--list {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.config-list-row .config-card__foot {
  grid-column: 1 / -1;
}

.config-empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 224px;
  padding: 24px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 8px;
  background: var(--app-overlay);
  color: var(--app-muted);
  text-align: center;
}

.config-empty strong {
  color: var(--app-text);
}

.dialog-intro {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}
.dialog-top-actions { display: flex; justify-content: flex-end; margin-bottom: 12px; }

.dialog-intro h3 {
  margin: 0;
  color: var(--app-text);
}

.dialog-intro p {
  margin: 5px 0 0;
  color: var(--app-muted);
  line-height: 1.5;
}

.dialog-form {
  display: grid;
  gap: 2px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-interactive);
}

.switch-row strong,
.switch-row span {
  display: block;
}

.switch-row strong {
  color: var(--app-text);
}

.switch-row span {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 13px;
}

@media (max-width: 720px) {
  .home-portal,
  .config-toolbar,
  .config-list-row,
  .switch-row {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .home-portal__flow,
  .home-portal__metrics {
    grid-template-columns: 1fr;
  }

  .home-portal {
    min-height: unset;
    padding: 24px;
  }

  .home-portal h1 {
    font-size: 36px;
  }

  .home-portal__headline {
    grid-template-columns: 92px minmax(0, 1fr);
    gap: 14px;
  }

  .home-portal__logo {
    width: 92px;
    height: 92px;
  }

  .home-portal__metrics {
    grid-template-columns: 1fr;
  }

  .home-portal__flow span:not(:last-child)::after {
    display: none;
  }

  .home-portal__flow {
    gap: 8px;
    padding: 10px;
  }

  .config-toolbar__actions {
    justify-content: stretch;
  }

  .config-toolbar__actions > * {
    width: 100%;
  }

  .form-grid,
  .config-stat-grid,
  .config-stat-grid--list {
    grid-template-columns: 1fr;
  }

  .config-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .config-card {
    min-height: unset;
    padding: 16px;
  }

  .config-card__head,
  .config-card__foot {
    align-items: flex-start;
  }
}
</style>
