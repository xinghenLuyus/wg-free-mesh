<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigRead, ControlLogRead, EndpointStatusRead, NodeRead, RealtimeEvent, RuntimeSnapshotItem } from '@/types/api'

const route = useRoute()
const router = useRouter()

const config = shallowRef<ConfigRead | null>(null)
const nodes = shallowRef<NodeRead[]>([])
const runtimeSnapshot = shallowRef<RuntimeSnapshotItem[]>([])
const selectedNodeId = shallowRef('')
const endpointStatus = shallowRef<EndpointStatusRead | null>(null)
const logs = shallowRef<ControlLogRead[]>([])

async function loadBase() {
  const configId = String(route.params.configId)
  const configs = await api.configs()
  config.value = configs.find((item) => item.id === configId) ?? null
  nodes.value = await api.nodes(configId)
  runtimeSnapshot.value = await api.runtimeSnapshot(configId)
  const preferredNodeId = typeof route.query.node === 'string' ? route.query.node : ''
  selectedNodeId.value = preferredNodeId || selectedNodeId.value || nodes.value[0]?.id || ''
  if (selectedNodeId.value) {
    await reloadNode()
  }
}

async function reloadNode() {
  const configId = String(route.params.configId)
  if (!selectedNodeId.value) return
  endpointStatus.value = await api.endpointStatus(configId, selectedNodeId.value)
  logs.value = await api.endpointLogs(configId, selectedNodeId.value)
}

async function sendAction(action: string) {
  try {
    const result = await api.controlEndpoint(String(route.params.configId), selectedNodeId.value, action)
    ElMessage.success(result.message)
    await reloadNode()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '控制命令失败')
  }
}

function selectNode(value: string) {
  selectedNodeId.value = value
}

const realtime = useRealtime((event: RealtimeEvent) => {
  const configId = String(route.params.configId)
  if (event.type === 'runtime.snapshot.updated' && event.payload.config_id === configId) {
    runtimeSnapshot.value = event.payload.items as RuntimeSnapshotItem[]
  }
  if (
    (event.type === 'runtime.node.updated' || event.type === 'control.log.created' || event.type === 'control.log.updated') &&
    event.payload.node_id === selectedNodeId.value
  ) {
    void reloadNode()
  }
})

watch(
  () => route.params.configId,
  async () => {
    selectedNodeId.value = ''
    await loadBase()
  },
)

watch(selectedNodeId, async (value) => {
  if (!value) return
  await router.replace({ path: route.path, query: { node: value } })
  await reloadNode()
})

onMounted(async () => {
  try {
    await loadBase()
    realtime.connect()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '端点状态加载失败')
  }
})
</script>

<template>
  <div class="ep-page">
    <div class="ep-shell">
      <div class="ep-shell-header">
        <div>
          <h2>{{ config?.name || '配置' }} - 端点控制</h2>
          <div class="ep-header-subtitle">运行快照、控制命令和日志统一收束在这一页。</div>
        </div>
        <div class="ep-header-actions">
          <el-tag :type="realtime.connected ? 'success' : 'warning'">
            {{ realtime.connected ? '实时连接正常' : '实时连接断开' }}
          </el-tag>
        </div>
      </div>

      <div class="ep-shell-body">
        <div class="ep-sidebar content-band">
          <div class="ep-sidebar-header"><h3>节点列表</h3></div>
          <el-menu :default-active="selectedNodeId" @select="selectNode">
            <el-menu-item v-for="node in nodes" :key="node.id" :index="node.id">
              {{ node.name }}
            </el-menu-item>
          </el-menu>
        </div>

        <div class="ep-main">
          <div v-if="endpointStatus" class="ep-panels">
            <div class="ep-card ep-status-card content-band">
              <div class="ep-card-title">运行状态</div>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="节点">{{ endpointStatus.node.name }}</el-descriptions-item>
                <el-descriptions-item label="类型">{{ endpointStatus.node.node_type }}</el-descriptions-item>
                <el-descriptions-item label="连通状态">{{ endpointStatus.runtime.connectivity_state }}</el-descriptions-item>
                <el-descriptions-item label="WG 状态">{{ endpointStatus.runtime.wg_runtime_state }}</el-descriptions-item>
                <el-descriptions-item label="同步状态">{{ endpointStatus.runtime.config_sync_state }}</el-descriptions-item>
                <el-descriptions-item label="服务端 Apply">{{ endpointStatus.config_state.server_apply_status }}</el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="ep-card content-band">
              <div class="ep-card-title">远程控制</div>
              <div class="ep-controls">
                <el-button @click="sendAction('start')">启动 WG</el-button>
                <el-button @click="sendAction('stop')">停止 WG</el-button>
                <el-button @click="sendAction('restart')">重启 WG</el-button>
                <el-button type="primary" @click="sendAction('sync')">同步配置</el-button>
              </div>
            </div>

            <div class="ep-card ep-log-card content-band">
              <div class="ep-log-header">
                <div class="ep-card-title">控制日志</div>
              </div>
              <div class="ep-log-list">
                <el-timeline>
                  <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="log.created_at">
                    {{ log.action }} / {{ log.status }} / {{ log.summary }}
                  </el-timeline-item>
                </el-timeline>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ep-shell { display: grid; gap: 20px; }
.ep-shell-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.ep-shell-header h2 { margin: 0; color: #1f2d28; font-size: 28px; }
.ep-header-subtitle { margin-top: 8px; color: #667972; }
.ep-shell-body { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }
.ep-main { display: grid; }
.ep-panels { display: grid; gap: 20px; }
.ep-sidebar-header h3, .ep-card-title { margin: 0 0 14px; }
.ep-controls { display: flex; flex-wrap: wrap; gap: 10px; }
@media (max-width: 1100px) { .ep-shell-body { grid-template-columns: 1fr; } }
</style>
