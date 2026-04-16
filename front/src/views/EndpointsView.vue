<script setup lang="ts">
import { RefreshRight, SwitchButton, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ControlLogEventPayload, ControlLogRead, EndpointStatusRead, EndpointStatusUpdatedPayload, RealtimeEvent } from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const route = useRoute()

const endpointStatus = shallowRef<EndpointStatusRead | null>(null)
const logs = shallowRef<ControlLogRead[]>([])

function nodeTypeLabel(type: 'dynamic' | 'static') {
  return type === 'static' ? '静态节点' : '动态节点'
}

async function reloadNode() {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  endpointStatus.value = await api.endpointStatus(configId, nodeId)
  logs.value = await api.endpointLogs(configId, nodeId)
}

async function sendAction(action: string) {
  try {
    const result = await api.controlEndpoint(String(route.params.configId), String(route.params.nodeId), action)
    notify.success(result.message)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '控制命令失败')
  }
}

function upsertLog(nextLog: ControlLogRead) {
  const items = [...logs.value]
  const index = items.findIndex((item) => item.id === nextLog.id)
  if (index >= 0) items[index] = nextLog
  else items.unshift(nextLog)
  logs.value = items.sort((left, right) => right.created_at.localeCompare(left.created_at))
}

const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'endpoint.status.updated') {
    const payload = event.payload as unknown as EndpointStatusUpdatedPayload
    if (payload.node_id === route.params.nodeId) {
      endpointStatus.value = payload.status
    }
  }
  if (event.type === 'control.log.created' || event.type === 'control.log.updated') {
    const payload = event.payload as unknown as ControlLogEventPayload
    if (payload.node_id === route.params.nodeId) {
      upsertLog(payload.log)
    }
  }
})

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    await reloadNode()
  },
)

onMounted(async () => {
  try {
    await reloadNode()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '端点状态加载失败')
  }
})
</script>

<template>
  <section class="node-template">
    <div class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>端点控制</h2>
          <p>查看当前节点运行状态、远程控制和控制日志。</p>
        </div>
        <el-tag :type="realtime.connected ? 'success' : 'warning'">
          {{ realtime.connected ? '实时连接正常' : '实时连接断开' }}
        </el-tag>
      </div>

      <div v-if="endpointStatus" class="endpoint-panels">
        <div class="endpoint-card">
          <div class="endpoint-card__title">运行状态</div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="节点">{{ endpointStatus.node.name }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ nodeTypeLabel(endpointStatus.node.node_type) }}</el-descriptions-item>
            <el-descriptions-item label="连通状态">{{ endpointStatus.runtime.connectivity_state }}</el-descriptions-item>
            <el-descriptions-item label="WG 状态">{{ endpointStatus.runtime.wg_runtime_state }}</el-descriptions-item>
            <el-descriptions-item label="Peer">{{ endpointStatus.runtime.peers_online }} / {{ endpointStatus.runtime.peers_total }}</el-descriptions-item>
            <el-descriptions-item label="最近在线">{{ formatDateTime(endpointStatus.runtime.last_seen) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="endpoint-card">
          <div class="endpoint-card__title">远程控制</div>
          <div class="endpoint-controls">
            <el-button :icon="VideoPlay" @click="sendAction('start')">启动 WG</el-button>
            <el-button :icon="VideoPause" @click="sendAction('stop')">停止 WG</el-button>
            <el-button :icon="RefreshRight" @click="sendAction('restart')">重启 WG</el-button>
            <el-button type="primary" :icon="SwitchButton" @click="sendAction('sync')">下发配置</el-button>
          </div>
        </div>

        <div class="endpoint-card">
          <div class="endpoint-card__title">控制日志</div>
          <el-timeline>
            <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="formatDateTime(log.created_at)">
              {{ log.action }} / {{ log.status }} / {{ log.summary }}
            </el-timeline-item>
          </el-timeline>
          <div v-if="!logs.length" class="empty-state">暂无日志</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.node-template { display: grid; gap: 20px; }
.template-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.template-toolbar h2 { margin: 0; color: var(--app-text); font-size: 22px; }
.template-toolbar p { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.endpoint-panels { display: grid; gap: 20px; }
.endpoint-card { display: grid; gap: 14px; padding: 16px; border: 1px solid #e0e8e4; border-radius: 8px; background: #ffffff; box-shadow: 0 8px 20px rgba(42, 65, 58, 0.045); }
.endpoint-card__title { color: #213029; font-size: 17px; font-weight: 750; }
.endpoint-controls { display: flex; flex-wrap: wrap; gap: 10px; }
.empty-state { display: grid; place-items: center; min-height: 120px; border: 1px dashed var(--app-border-strong); border-radius: 8px; color: var(--app-muted); }
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } }
</style>
