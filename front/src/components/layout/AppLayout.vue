<script setup lang="ts">
import { Files, House, InfoFilled, Setting, SwitchButton } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type { ConfigListUpdatedPayload, ConfigRead, HealthRead, RealtimeEvent, SystemStatusRead } from '@/types/api'
import { setSystemTimeZone } from '@/utils/dateTime'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()

const configs = shallowRef<ConfigRead[]>([])
const systemStatus = shallowRef<SystemStatusRead | null>(null)
const health = shallowRef<HealthRead | null>(null)
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'config.list.updated') {
    configs.value = (event.payload as unknown as ConfigListUpdatedPayload).configs
  }
  if (event.type === 'system.status.updated' && event.payload) {
    systemStatus.value = event.payload as unknown as SystemStatusRead
  }
})

const topItems = computed(() => [
  { path: '/', label: t('layout.home'), icon: House },
  { path: '/settings', label: t('layout.settings'), icon: Setting },
  { path: '/help', label: t('layout.help'), icon: InfoFilled },
])

const currentPath = computed(() => route.path)
const systemStatusText = computed(() => {
  if (health.value?.dev_test_api_enabled) return t('layout.runningDev')
  if (!systemStatus.value) return t('layout.checking')
  if (systemStatus.value.summary.pending_sync_nodes > 0) return t('layout.pendingSync')
  if (systemStatus.value.summary.online_nodes > 0) return t('layout.running')
  return t('layout.waiting')
})
const systemStatusMeta = computed(() => {
  if (!systemStatus.value) return t('layout.statusMetaEmpty')
  return t('layout.statusMeta', {
    online: systemStatus.value.summary.online_nodes,
    pending: systemStatus.value.summary.pending_sync_nodes,
  })
})
const systemStatusType = computed<'success' | 'warning' | 'info'>(() => {
  if (!systemStatus.value) return 'info'
  if (systemStatus.value.summary.pending_sync_nodes > 0) return 'warning'
  if (systemStatus.value.summary.online_nodes > 0) return 'success'
  return 'info'
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

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

onMounted(() => {
  void preferencesStore.load()
  void loadConfigs()
  void loadSystemStatus()
  void loadHealth()
  void loadSystemTimezone()
  realtime.connect()
})
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar__brand">
        <h2>WG Free Mesh</h2>
        <div class="sidebar__brand-meta">{{ brandMeta }}</div>
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
            :class="{ 'sidebar-link--active': isConfigActive(config.id) }"
          >
            <el-icon><Files /></el-icon>
            <span>{{ config.name }}</span>
          </RouterLink>
        </div>

        <div class="sidebar-divider"></div>
        <button class="sidebar-logout" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>{{ t('layout.logout') }}</span>
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
.sidebar__brand { padding: 26px 22px 18px; border-bottom: 1px solid var(--app-border-soft); }
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
