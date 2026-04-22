<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { HealthRead, RealtimeEvent, SystemClockSyncPayload, SystemStatusRead } from '@/types/api'
import { formatDateTime, setSystemTimeZone } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const { t } = useI18n()
const router = useRouter()
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
  if (realtime.state.value === 'connected' && realtime.connected.value) return t('system.connected')
  if (realtime.state.value === 'connecting') return t('system.connecting')
  if (realtime.state.value === 'reconnecting') return t('system.reconnecting')
  if (realtime.state.value === 'degraded') return t('system.degraded')
  return t('system.disconnected')
})
const realtimeBannerType = computed(() => (realtime.connected.value ? 'success' : 'warning'))
const realtimeBannerText = computed(() => (realtime.connected.value ? t('system.realtimeOk') : t('system.realtimeDown')))
const topologyHealthy = computed(() => status.value?.topology.valid !== false)

function syncServerClock(timestamp: string | null | undefined) {
  if (!timestamp) return
  const parsed = new Date(timestamp).getTime()
  if (Number.isNaN(parsed)) return
  serverClockBaseMs.value = parsed
  serverClockReceivedMs.value = Date.now()
  displayNowMs.value = Date.now()
}

function openConfig(configId: string) {
  void router.push(`/configs/${configId}`)
}

const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'system.clock.sync' && health.value) {
    const payload = event.payload as unknown as SystemClockSyncPayload
    if (payload.timezone) {
      setSystemTimeZone(payload.timezone)
    }
    health.value = { ...health.value, timestamp: payload.timestamp }
    syncServerClock(payload.timestamp)
  }
  if (event.type === 'system.status.updated' && event.payload) {
    status.value = event.payload as unknown as SystemStatusRead
  }
})

async function load() {
  health.value = await api.health()
  setSystemTimeZone(health.value.timezone)
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
    notify.error(error instanceof ApiClientError ? error.message : t('system.loadFailed'))
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
        <h1 class="page-title">{{ t('system.title') }}</h1>
        <p class="page-description">{{ t('system.description') }}</p>
      </div>
      <el-tag :type="realtimeBannerType">
        {{ realtimeBannerText }}
      </el-tag>
    </div>
  </section>

  <section v-if="health" class="content-band section-gap">
    <el-descriptions :column="1" border :title="t('system.health')">
      <el-descriptions-item :label="t('system.status')">{{ health.status }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.service')">{{ health.service }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.version')">{{ health.version }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.time')">{{ serverClockText }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.timezone')">{{ health.timezone }}</el-descriptions-item>
    </el-descriptions>
  </section>

  <section v-if="status" class="content-band section-gap">
    <el-descriptions :column="1" border :title="t('system.summary')">
      <el-descriptions-item :label="t('system.configs')">{{ status.summary.configs }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.nodes')">{{ status.summary.nodes }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.onlineNodes')">{{ status.summary.online_nodes }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.pendingSyncNodes')">{{ status.summary.pending_sync_nodes }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.database')">{{ status.services.database }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.mqtt')">{{ status.services.mqtt }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.realtimeState')">
        {{ streamConnectionText }}
      </el-descriptions-item>
    </el-descriptions>
  </section>

  <section v-if="status" class="content-band section-gap">
    <div class="topology-head">
      <h2>{{ t('system.topologyTitle') }}</h2>
      <el-tag :type="topologyHealthy ? 'success' : 'danger'">
        {{ topologyHealthy ? t('system.topologyHealthy') : t('system.topologyFailed') }}
      </el-tag>
    </div>
    <el-descriptions :column="1" border :title="t('system.topologySummary')">
      <el-descriptions-item :label="t('system.topologyConfigs')">{{ status.topology.invalid_config_count }}</el-descriptions-item>
      <el-descriptions-item :label="t('system.topologyNodes')">{{ status.topology.invalid_node_count }}</el-descriptions-item>
    </el-descriptions>

    <div v-if="status.topology.invalid_configs.length" class="topology-list">
      <button
        v-for="item in status.topology.invalid_configs"
        :key="item.config_id"
        class="topology-card"
        @click="openConfig(item.config_id)"
      >
        <div class="topology-card__head">
          <strong>{{ item.config_name }}</strong>
          <el-tag type="danger" size="small">{{ t('system.topologyConfigFailed') }}</el-tag>
        </div>
        <div class="topology-card__meta">
          <span>{{ t('system.topologyConfigErrors', { count: item.error_count }) }}</span>
          <span>{{ t('system.topologyConfigNodes', { count: item.invalid_node_count }) }}</span>
        </div>
        <p>{{ item.errors[0] }}</p>
      </button>
    </div>
    <div v-else class="topology-empty">{{ t('system.topologyEmpty') }}</div>
  </section>
</template>

<style scoped>
.content-card {
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface) 0%, var(--app-surface-sunken) 100%);
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

.topology-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.topology-head h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 22px;
}

.topology-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.topology-card {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 16px;
  border: 1px solid var(--app-danger-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--app-danger-border) 10%, var(--app-surface-elevated));
  text-align: left;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}

.topology-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--app-shadow-md);
  border-color: color-mix(in srgb, var(--app-danger-border) 88%, var(--app-primary));
}

.topology-card:focus-visible {
  outline: 0;
  box-shadow: var(--app-focus), var(--app-shadow-md);
}

.topology-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.topology-card__head strong {
  color: var(--app-text-strong);
  font-size: 16px;
}

.topology-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--app-danger-text);
  font-size: 13px;
  font-weight: 650;
}

.topology-card p,
.topology-empty {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.6;
}

@media (max-width: 720px) {
  .page-header,
  .topology-head,
  .topology-card__head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
