<script setup lang="ts">
import { Files, House, InfoFilled, Setting, SwitchButton } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import type { ConfigRead, SystemStatusRead } from '@/types/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const configs = shallowRef<ConfigRead[]>([])
const systemStatus = shallowRef<SystemStatusRead | null>(null)

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

function configLinks(configId: string) {
  return [
    { path: `/configs/${configId}`, label: '概览' },
    { path: `/configs/${configId}/mesh`, label: 'Mesh网络' },
    { path: `/configs/${configId}/apply`, label: '配置应用' },
    { path: `/configs/${configId}/endpoints`, label: '端点控制' },
  ]
}

function isConfigOpen(configId: string) {
  return currentPath.value.startsWith(`/configs/${configId}`)
}

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadConfigs()
  void loadSystemStatus()
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
          <div v-for="config in configs" :key="config.id" class="sidebar-config">
            <RouterLink
              :to="`/configs/${config.id}`"
              class="sidebar-link sidebar-link--config"
              :class="{ 'sidebar-link--active': isConfigOpen(config.id) }"
            >
              <el-icon><Files /></el-icon>
              <span>{{ config.name }}</span>
            </RouterLink>
            <div v-if="isConfigOpen(config.id)" class="sidebar-submenu">
              <RouterLink
                v-for="item in configLinks(config.id)"
                :key="item.path"
                :to="item.path"
                class="sidebar-sublink"
                :class="{ 'sidebar-sublink--active': currentPath === item.path }"
              >
                {{ item.label }}
              </RouterLink>
            </div>
          </div>
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
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: 260px 1fr; min-height: 100vh; background: #f5f7f6; }
.sidebar { display: flex; flex-direction: column; border-right: 1px solid #d8e1dd; background: #fff; }
.sidebar__brand { padding: 22px 20px 18px; border-bottom: 1px solid #d8e1dd; }
.sidebar__brand h2 { margin: 0; font-size: 22px; color: #1f2d28; }
.sidebar__nav { flex: 1 1 auto; display: flex; flex-direction: column; gap: 4px; padding: 12px 12px 20px; }
.sidebar-link, .sidebar-sublink, .sidebar-logout {
  display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 12px; border: 0;
  border-radius: 8px; color: #4b5f58; background: transparent; text-decoration: none; font: inherit; cursor: pointer; text-align: left;
}
.sidebar-link--active, .sidebar-sublink--active { color: #0f8b8d; background: #eef8f7; }
.sidebar-divider { height: 1px; margin: 10px 8px; background: #e0e8e4; }
.sidebar-section { padding: 4px 12px 8px; color: #7a8c85; font-size: 12px; }
.sidebar-configs, .sidebar-config { display: grid; gap: 4px; }
.sidebar-submenu { display: grid; gap: 2px; margin-left: 14px; }
.sidebar-sublink { padding: 8px 12px; font-size: 14px; }
.sidebar-system-status { margin: 0 12px 14px; padding: 14px 12px; border: 1px solid #d8e1dd; border-radius: 8px; background: #f8fbf9; text-align: left; cursor: pointer; }
.sidebar-system-status__main { display: flex; align-items: center; gap: 8px; }
.sidebar-system-status__dot { width: 10px; height: 10px; border-radius: 999px; background: #9aa9a3; }
.sidebar-system-status__dot[data-type='success'] { background: #2f9e44; }
.sidebar-system-status__dot[data-type='warning'] { background: #d98c21; }
.sidebar-system-status__text { color: #213029; font-size: 13px; font-weight: 600; }
.sidebar-system-status__meta { margin-top: 8px; color: #6d8079; font-size: 12px; }
.main { padding: 24px; }
@media (max-width: 960px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid #d8e1dd; }
}
</style>
