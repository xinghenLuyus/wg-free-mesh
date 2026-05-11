<script setup lang="ts">
import { Download, Files, House, InfoFilled, Setting, SwitchButton } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import { useRealtime } from '@/composables/useRealtime'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type {
  ConfigListUpdatedPayload,
  ConfigOverviewUpdatedPayload,
  ConfigRead,
  HealthRead,
  RealtimeEvent,
  SystemStatusRead,
} from '@/types/api'
import { setSystemTimeZone } from '@/utils/dateTime'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()
const actions = useAsyncActionGroup()
const loggingOut = actions.isPending('logout')

const configs = shallowRef<ConfigRead[]>([])
const systemStatus = shallowRef<SystemStatusRead | null>(null)
const health = shallowRef<HealthRead | null>(null)
let lastRealtimeVersion = 0

function patchConfig(configId: string, patch: Partial<ConfigRead>) {
  configs.value = configs.value.map((config) => (config.id === configId ? { ...config, ...patch } : config))
}

function syncConfigTopologyFromSystemStatus(status: SystemStatusRead) {
  const invalidMap = new Map(status.topology.invalid_configs.map((item) => [item.config_id, item.error_count]))
  configs.value = configs.value.map((config) => ({
    ...config,
    topology_invalid: invalidMap.has(config.id),
    topology_error_count: invalidMap.get(config.id) ?? 0,
  }))
}

function patchSystemTopologyFromOverview(payload: ConfigOverviewUpdatedPayload) {
  if (!systemStatus.value) return

  const invalidConfigs = systemStatus.value.topology.invalid_configs.filter((item) => item.config_id !== payload.config_id)
  if (payload.overview.config.enabled && !payload.overview.topology.valid) {
    invalidConfigs.push({
      config_id: payload.config_id,
      config_name: payload.overview.config.name,
      error_count: payload.overview.topology.error_count,
      invalid_node_count: payload.overview.topology.invalid_node_count,
      errors: payload.overview.topology.errors,
    })
  }

  const invalidNodeCount = invalidConfigs.reduce((count, item) => count + item.invalid_node_count, 0)
  systemStatus.value = {
    ...systemStatus.value,
    topology: {
      valid: invalidConfigs.length === 0,
      invalid_config_count: invalidConfigs.length,
      invalid_node_count: invalidNodeCount,
      invalid_configs: invalidConfigs,
    },
  }
}

const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'config.list.updated') {
    configs.value = (event.payload as unknown as ConfigListUpdatedPayload).configs
  }
  if (event.type === 'config.overview.updated' && event.payload) {
    const payload = event.payload as unknown as ConfigOverviewUpdatedPayload
    patchConfig(payload.config_id, {
      name: payload.overview.config.name,
      description: payload.overview.config.description,
      enabled: payload.overview.config.enabled,
      topology_invalid: !payload.overview.topology.valid && payload.overview.config.enabled,
      topology_error_count: payload.overview.config.enabled ? payload.overview.topology.error_count : 0,
      updated_at: payload.overview.config.updated_at,
    })
    patchSystemTopologyFromOverview(payload)
  }
  if (event.type === 'system.status.updated' && event.payload) {
    systemStatus.value = event.payload as unknown as SystemStatusRead
    syncConfigTopologyFromSystemStatus(systemStatus.value)
  }
})

const topItems = computed(() => [
  { path: '/', label: t('layout.home'), icon: House },
  { path: '/settings', label: t('layout.settings'), icon: Setting },
  { path: '/help', label: t('layout.help'), icon: InfoFilled },
])
const toolItems = computed(() => [
  { path: '/tools/download', label: t('layout.download'), icon: Download },
])

const currentPath = computed(() => route.path)
const systemStatusText = computed(() => {
  if (systemStatus.value?.topology.invalid_config_count) return t('layout.meshAlert')
  if (systemStatus.value?.services.mqtt === 'error') return t('layout.mqttError')
  if (systemStatus.value?.services.mqtt === 'disabled') return t('layout.mqttDisabled')
  if (health.value?.dev_test_api_enabled) return t('layout.runningDev')
  if (!systemStatus.value) return t('layout.checking')
  if (systemStatus.value.summary.pending_sync_nodes > 0) return t('layout.pendingSync')
  if (systemStatus.value.summary.online_nodes > 0) return t('layout.running')
  return t('layout.waiting')
})
const systemStatusMeta = computed(() => {
  if (!systemStatus.value) return t('layout.statusMetaEmpty')
  if (systemStatus.value.topology.invalid_config_count > 0) {
    return t('layout.meshAlertMeta', {
      configs: systemStatus.value.topology.invalid_config_count,
      nodes: systemStatus.value.topology.invalid_node_count,
    })
  }
  if (systemStatus.value.services.mqtt === 'error') return t('layout.mqttErrorMeta')
  if (systemStatus.value.services.mqtt === 'disabled') return t('layout.mqttDisabledMeta')
  return t('layout.statusMeta', {
    online: systemStatus.value.summary.online_nodes,
    pending: systemStatus.value.summary.pending_sync_nodes,
  })
})
const systemStatusType = computed<'success' | 'warning' | 'info' | 'danger'>(() => {
  if (!systemStatus.value) return 'info'
  if (systemStatus.value.topology.invalid_config_count > 0) return 'danger'
  if (systemStatus.value.services.mqtt === 'error') return 'warning'
  if (systemStatus.value.services.mqtt === 'disabled') return 'info'
  if (health.value?.dev_test_api_enabled) return 'success'
  if (systemStatus.value.summary.pending_sync_nodes > 0) return 'warning'
  if (systemStatus.value.summary.online_nodes > 0) return 'success'
  return 'success'
})
const brandMeta = computed(() => (health.value?.version ? `${t('common.console')} · v${health.value.version}` : t('common.console')))

async function loadConfigs() {
  configs.value = await api.configs()
}

async function loadSystemStatus() {
  systemStatus.value = await api.systemStatus()
}

async function loadHealth() {
  health.value = await api.health()
  setSystemTimeZone(health.value.timezone)
}

async function loadSystemTimezone() {
  const timezone = await api.systemTimezone()
  setSystemTimeZone(timezone.timezone)
}

function isConfigActive(configId: string) {
  return currentPath.value.startsWith(`/configs/${configId}`)
}

function isToolActive(path: string) {
  return currentPath.value === path || currentPath.value.startsWith(`${path}/`)
}

async function handleLogout() {
  await actions.run('logout', async () => {
    await authStore.logout()
    await router.push('/login')
  })
}

onMounted(() => {
  void preferencesStore.load()
  void loadConfigs()
  void loadSystemStatus()
  void loadHealth()
  void loadSystemTimezone()
  realtime.connect()
  lastRealtimeVersion = realtime.connectionVersion.value
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
    await Promise.allSettled([loadConfigs(), loadSystemStatus(), loadHealth()])
  },
)
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar__brand">
        <img class="sidebar__brand-logo" src="/logo.png" alt="WG Free Mesh" />
        <div class="sidebar__brand-copy">
          <h2>WG Free Mesh</h2>
          <div class="sidebar__brand-meta">{{ brandMeta }}</div>
        </div>
      </div>

      <nav class="sidebar__nav">
        <RouterLink
          v-for="item in topItems"
          :key="item.path"
          :to="item.path"
          class="sidebar-link"
          :class="{ 'sidebar-link--active': currentPath === item.path }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>

        <div class="sidebar-divider"></div>
        <div class="sidebar-section">{{ t('layout.configList') }}</div>

        <div class="sidebar-configs">
          <RouterLink
            v-for="config in configs"
            :key="config.id"
            :to="`/configs/${config.id}`"
            class="sidebar-link sidebar-link--config"
            :class="{
              'sidebar-link--active': isConfigActive(config.id),
              'sidebar-link--danger': config.topology_invalid,
            }"
          >
            <el-icon><Files /></el-icon>
            <span>{{ config.name }}</span>
            <span v-if="config.topology_invalid" class="sidebar-link__alert-dot" :title="t('configOverview.topologyFailed')"></span>
          </RouterLink>
        </div>

        <div class="sidebar-divider"></div>
        <div class="sidebar-section">{{ t('layout.toolList') }}</div>

        <div class="sidebar-configs">
          <RouterLink
            v-for="item in toolItems"
            :key="item.path"
            :to="item.path"
            class="sidebar-link"
            :class="{ 'sidebar-link--active': isToolActive(item.path) }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>

        <div class="sidebar-divider"></div>
        <button class="sidebar-logout" :disabled="loggingOut" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>{{ loggingOut ? t('common.loading') : t('layout.logout') }}</span>
        </button>
      </nav>

      <button class="sidebar-system-status" @click="router.push('/system')">
        <div class="sidebar-system-status__main">
          <span class="sidebar-system-status__dot" :data-type="systemStatusType"></span>
          <span class="sidebar-system-status__text">{{ systemStatusText }}</span>
        </div>
        <div class="sidebar-system-status__meta">{{ systemStatusMeta }}</div>
      </button>
    </aside>

    <main class="main">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="route-panel" appear>
          <component
            :is="Component"
            :key="`${viewRoute.matched[1]?.path || viewRoute.path}:${String(viewRoute.params.configId || '')}`"
          />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: 292px minmax(0, 1fr); min-height: 100vh; padding: 14px; gap: 14px; background: transparent; }
.sidebar {
  position: sticky;
  top: 14px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 28px);
  min-height: 0;
  border: 1px solid color-mix(in srgb, var(--app-border) 96%, transparent);
  border-radius: 18px;
  background: var(--app-overlay);
  backdrop-filter: blur(12px);
  box-shadow: var(--app-shadow-md);
  overflow: hidden;
}
.sidebar__brand { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 22px 22px 18px; border-bottom: 1px solid var(--app-border-soft); }
.sidebar__brand-logo { flex: 0 0 auto; width: 42px; height: 42px; object-fit: contain; }
.sidebar__brand-copy { min-width: 0; }
.sidebar__brand h2 { margin: 0; color: var(--app-text-strong); font-size: 22px; line-height: 1.15; letter-spacing: 0; }
.sidebar__brand-meta { margin-top: 6px; color: var(--app-muted); font-size: 12px; font-weight: 600; }
.sidebar__nav { flex: 1 1 auto; display: flex; flex-direction: column; gap: 6px; overflow: auto; padding: 16px 14px 20px; }
.sidebar-link, .sidebar-logout {
  display: flex; align-items: center; gap: 10px; width: 100%; min-height: 42px; padding: 10px 12px; border: 1px solid transparent;
  border-radius: 8px; color: color-mix(in srgb, var(--app-text) 72%, var(--app-muted)); background: transparent; text-decoration: none; font: inherit; cursor: pointer; text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}
.sidebar-link:hover, .sidebar-logout:hover { transform: translateX(2px); border-color: var(--app-border-soft); background: var(--app-surface-interactive); color: var(--app-text); }
.sidebar-link:focus-visible, .sidebar-logout:focus-visible, .sidebar-system-status:focus-visible { outline: 0; box-shadow: var(--app-focus); }
.sidebar-link--active { color: var(--app-primary-strong); border-color: var(--app-border-accent); background: var(--app-surface-selected); font-weight: 750; }
.sidebar-link .el-icon, .sidebar-logout .el-icon { font-size: 17px; }
.sidebar-divider { height: 1px; margin: 12px 10px; background: var(--app-border-soft); }
.sidebar-section { padding: 4px 12px 8px; color: var(--app-faint); font-size: 12px; font-weight: 800; letter-spacing: 0; }
.sidebar-configs { display: grid; gap: 5px; }
.sidebar-link--config span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sidebar-link--danger { border-color: color-mix(in srgb, var(--app-danger-border) 58%, transparent); color: color-mix(in srgb, var(--app-danger-text) 76%, var(--app-text)); }
.sidebar-link--danger:hover { border-color: var(--app-danger-border); background: color-mix(in srgb, var(--app-danger-border) 10%, var(--app-surface-interactive)); color: var(--app-danger-text); }
.sidebar-link__alert-dot { flex: 0 0 auto; width: 8px; height: 8px; margin-left: auto; border-radius: 999px; background: var(--app-danger-text); box-shadow: 0 0 0 4px color-mix(in srgb, var(--app-danger-text) 14%, transparent); }
.sidebar-system-status {
  margin: 0 14px 14px;
  padding: 16px 14px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--app-shadow-sm);
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}
.sidebar-system-status:hover { transform: translateY(-1px); border-color: var(--app-border-accent); box-shadow: var(--app-shadow-md); }
.sidebar-system-status__main { display: flex; align-items: center; gap: 8px; }
.sidebar-system-status__dot { width: 10px; height: 10px; border-radius: 999px; background: var(--app-faint); box-shadow: 0 0 0 4px color-mix(in srgb, var(--app-faint) 12%, transparent); }
.sidebar-system-status__dot[data-type='success'] { background: var(--el-color-success); box-shadow: 0 0 0 4px color-mix(in srgb, var(--el-color-success) 13%, transparent); }
.sidebar-system-status__dot[data-type='warning'] { background: var(--el-color-warning); box-shadow: 0 0 0 4px color-mix(in srgb, var(--el-color-warning) 13%, transparent); }
.sidebar-system-status__dot[data-type='danger'] { background: var(--app-danger-text); box-shadow: 0 0 0 4px color-mix(in srgb, var(--app-danger-text) 16%, transparent); }
.sidebar-system-status__text { color: var(--app-text-strong); font-size: 13px; font-weight: 750; }
.sidebar-system-status__meta { margin-top: 8px; color: var(--app-muted); font-size: 12px; }
.main { min-width: 0; padding: 12px 12px 12px 0; }
@media (max-width: 960px) {
  .shell { grid-template-columns: 1fr; padding: 0; gap: 0; }
  .sidebar { position: static; top: auto; height: auto; min-height: auto; border: 0; border-bottom: 1px solid var(--app-border); border-radius: 0; box-shadow: none; }
  .sidebar__nav { overflow: visible; }
  .main { padding: 18px; }
}
</style>
