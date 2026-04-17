<script setup lang="ts">
import { Files, House, InfoFilled, Setting, SwitchButton } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import { useAuthStore } from '@/stores/auth'
import type { ConfigListUpdatedPayload, ConfigRead, RealtimeEvent, SystemStatusRead } from '@/types/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const configs = shallowRef<ConfigRead[]>([])
const systemStatus = shallowRef<SystemStatusRead | null>(null)
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'config.list.updated') {
    configs.value = (event.payload as unknown as ConfigListUpdatedPayload).configs
  }
  if (event.type === 'system.status.updated' && event.payload) {
    systemStatus.value = event.payload as unknown as SystemStatusRead
  }
})

const topItems = [
  { path: '/', label: '首页', icon: House },
  { path: '/settings', label: '设置', icon: Setting },
  { path: '/help', label: '帮助', icon: InfoFilled },
]

const currentPath = computed(() => route.path)
const systemStatusText = computed(() => {
  if (!systemStatus.value) return '系统状态检测中...'
  if (systemStatus.value.summary.pending_sync_nodes > 0) return '存在待同步节点'
  if (systemStatus.value.summary.online_nodes > 0) return '系统运行中'
  return '等待端点上线'
})
const systemStatusMeta = computed(() => {
  if (!systemStatus.value) return '点击查看状态详情'
  return `在线 ${systemStatus.value.summary.online_nodes} / 待同步 ${systemStatus.value.summary.pending_sync_nodes}`
})
const systemStatusType = computed<'success' | 'warning' | 'info'>(() => {
  if (!systemStatus.value) return 'info'
  if (systemStatus.value.summary.pending_sync_nodes > 0) return 'warning'
  if (systemStatus.value.summary.online_nodes > 0) return 'success'
  return 'info'
})

async function loadConfigs() {
  configs.value = await api.configs()
}

async function loadSystemStatus() {
  systemStatus.value = await api.systemStatus()
}

function isConfigActive(configId: string) {
  return currentPath.value.startsWith(`/configs/${configId}`)
}

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadConfigs()
  void loadSystemStatus()
  realtime.connect()
})
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="sidebar__brand">
        <h2>WG Free Mesh</h2>
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
        <div class="sidebar-section">配置列表</div>

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
          <span>退出登录</span>
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
  border: 1px solid rgba(216, 225, 221, 0.96);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  box-shadow: 0 20px 44px rgba(42, 65, 58, 0.11);
  overflow: hidden;
}
.sidebar__brand { padding: 26px 22px 18px; border-bottom: 1px solid #e5ece9; }
.sidebar__brand h2 { margin: 0; color: #1f2d28; font-size: 22px; line-height: 1.15; letter-spacing: 0; }
.sidebar__brand h2::after { content: "控制台"; display: block; margin-top: 6px; color: var(--app-muted); font-size: 12px; font-weight: 600; }
.sidebar__nav { flex: 1 1 auto; display: flex; flex-direction: column; gap: 6px; overflow: auto; padding: 16px 14px 20px; }
.sidebar-link, .sidebar-logout {
  display: flex; align-items: center; gap: 10px; width: 100%; min-height: 42px; padding: 10px 12px; border: 1px solid transparent;
  border-radius: 8px; color: #4b5f58; background: transparent; text-decoration: none; font: inherit; cursor: pointer; text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}
.sidebar-link:hover, .sidebar-logout:hover { transform: translateX(2px); border-color: #dce7e3; background: #f7fbf9; color: #24352f; }
.sidebar-link:focus-visible, .sidebar-logout:focus-visible, .sidebar-system-status:focus-visible { outline: 0; box-shadow: var(--app-focus); }
.sidebar-link--active { color: #0f7375; border-color: #bfe0da; background: #eaf7f5; font-weight: 750; }
.sidebar-link .el-icon, .sidebar-logout .el-icon { font-size: 17px; }
.sidebar-divider { height: 1px; margin: 12px 10px; background: #e0e8e4; }
.sidebar-section { padding: 4px 12px 8px; color: #7a8c85; font-size: 12px; font-weight: 800; letter-spacing: 0; }
.sidebar-configs { display: grid; gap: 5px; }
.sidebar-link--config span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sidebar-system-status {
  margin: 0 14px 14px;
  padding: 16px 14px;
  border: 1px solid #d8e1dd;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbf9 100%);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--app-shadow-sm);
}
.sidebar-system-status__main { display: flex; align-items: center; gap: 8px; }
.sidebar-system-status__dot { width: 10px; height: 10px; border-radius: 999px; background: #9aa9a3; box-shadow: 0 0 0 4px rgba(154, 169, 163, 0.12); }
.sidebar-system-status__dot[data-type='success'] { background: #2f9e44; box-shadow: 0 0 0 4px rgba(47, 158, 68, 0.13); }
.sidebar-system-status__dot[data-type='warning'] { background: #d98c21; box-shadow: 0 0 0 4px rgba(217, 140, 33, 0.13); }
.sidebar-system-status__text { color: #213029; font-size: 13px; font-weight: 750; }
.sidebar-system-status__meta { margin-top: 8px; color: #6d8079; font-size: 12px; }
.main { min-width: 0; padding: 12px 12px 12px 0; }
@media (max-width: 960px) {
  .shell { grid-template-columns: 1fr; padding: 0; gap: 0; }
  .sidebar { position: static; top: auto; height: auto; min-height: auto; border: 0; border-bottom: 1px solid #d8e1dd; border-radius: 0; box-shadow: none; }
  .sidebar__nav { overflow: visible; }
  .main { padding: 18px; }
}
</style>
