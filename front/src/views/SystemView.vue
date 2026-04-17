<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { HealthRead, RealtimeEvent, SystemClockSyncPayload, SystemStatusRead } from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const health = shallowRef<HealthRead | null>(null)
const status = shallowRef<SystemStatusRead | null>(null)
const serverClockBaseMs = shallowRef<number | null>(null)
const serverClockReceivedMs = shallowRef<number | null>(null)
const displayNowMs = shallowRef(Date.now())
let displayTimer: number | null = null

const serverClockText = computed(() => {
  if (serverClockBaseMs.value === null || serverClockReceivedMs.value === null) {
    return formatDateTime(health.value?.timestamp)
  }
  const current = serverClockBaseMs.value + (displayNowMs.value - serverClockReceivedMs.value)
  return formatDateTime(new Date(current))
})

const streamConnectionText = computed(() => {
  if (realtime.state.value === 'connected' && realtime.connected.value) return '已连接'
  if (realtime.state.value === 'connecting') return '连接中'
  if (realtime.state.value === 'reconnecting') return '重连中'
  if (realtime.state.value === 'degraded') return '连接异常'
  return '已断开'
})
const realtimeBannerType = computed(() => (realtime.connected.value ? 'success' : 'warning'))
const realtimeBannerText = computed(() => (realtime.connected.value ? '实时同步正常' : '实时同步断开'))

function syncServerClock(timestamp: string | null | undefined) {
  if (!timestamp) return
  const parsed = new Date(timestamp).getTime()
  if (Number.isNaN(parsed)) return
  serverClockBaseMs.value = parsed
  serverClockReceivedMs.value = Date.now()
  displayNowMs.value = Date.now()
}

const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'system.clock.sync' && health.value) {
    const payload = event.payload as unknown as SystemClockSyncPayload
    health.value = { ...health.value, timestamp: payload.timestamp }
    syncServerClock(payload.timestamp)
  }
  if (event.type === 'system.status.updated' && event.payload) {
    status.value = event.payload as unknown as SystemStatusRead
  }
})

async function load() {
  health.value = await api.health()
  status.value = await api.systemStatus()
  syncServerClock(health.value.timestamp)
}

onMounted(async () => {
  displayTimer = window.setInterval(() => {
    displayNowMs.value = Date.now()
  }, 1000)
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '系统状态加载失败')
  }
})

onBeforeUnmount(() => {
  if (displayTimer !== null) {
    window.clearInterval(displayTimer)
    displayTimer = null
  }
})
</script>

<template>
  <section class="content-card">
    <div class="page-header">
      <div>
        <h1 class="page-title">系统状态</h1>
        <p class="page-description">这里查看健康检查和服务聚合状态。</p>
      </div>
      <el-tag :type="realtimeBannerType">
        {{ realtimeBannerText }}
      </el-tag>
    </div>
  </section>

  <section v-if="health" class="content-band section-gap">
    <el-descriptions :column="1" border title="健康检查">
      <el-descriptions-item label="状态">{{ health.status }}</el-descriptions-item>
      <el-descriptions-item label="服务">{{ health.service }}</el-descriptions-item>
      <el-descriptions-item label="版本">{{ health.version }}</el-descriptions-item>
      <el-descriptions-item label="时间">{{ serverClockText }}</el-descriptions-item>
    </el-descriptions>
  </section>

  <section v-if="status" class="content-band section-gap">
    <el-descriptions :column="1" border title="聚合状态">
      <el-descriptions-item label="配置数">{{ status.summary.configs }}</el-descriptions-item>
      <el-descriptions-item label="节点数">{{ status.summary.nodes }}</el-descriptions-item>
      <el-descriptions-item label="在线节点">{{ status.summary.online_nodes }}</el-descriptions-item>
      <el-descriptions-item label="待同步节点">{{ status.summary.pending_sync_nodes }}</el-descriptions-item>
      <el-descriptions-item label="数据库">{{ status.services.database }}</el-descriptions-item>
      <el-descriptions-item label="MQTT">{{ status.services.mqtt }}</el-descriptions-item>
      <el-descriptions-item label="实时连接状态">
        {{ streamConnectionText }}
      </el-descriptions-item>
    </el-descriptions>
  </section>
</template>

<style scoped>
.content-card {
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbf9 100%);
  box-shadow: var(--app-shadow-md);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  margin: 0;
  color: var(--app-text);
  font-size: 30px;
}

.page-description {
  margin: 8px 0 0;
  color: var(--app-muted);
  line-height: 1.6;
}

.section-gap {
  margin-top: 20px;
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
