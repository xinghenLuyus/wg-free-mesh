<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead, NodeRead, SyncStatusRead } from '@/types/api'

const route = useRoute()
const router = useRouter()

const config = shallowRef<ConfigRead | null>(null)
const nodes = shallowRef<NodeRead[]>([])
const syncItems = shallowRef<SyncStatusRead[]>([])
const selectedNodeId = shallowRef('')
const previewContent = shallowRef('')
const appliedState = reactive({
  content: '',
  exists: false,
  node_name: '',
  node_type: '',
  desired_version: 0,
  staged_version: 0,
})

const selectedSync = computed(() => syncItems.value.find((item) => item.node_id === selectedNodeId.value) ?? null)

async function loadBase() {
  const configId = String(route.params.configId)
  const configs = await api.configs()
  config.value = configs.find((item) => item.id === configId) ?? null
  nodes.value = await api.nodes(configId)
  syncItems.value = await api.syncStatuses(configId)
  const preferredNodeId = typeof route.query.node === 'string' ? route.query.node : ''
  selectedNodeId.value = preferredNodeId || selectedNodeId.value || nodes.value[0]?.id || ''
  if (selectedNodeId.value) {
    await loadNodeState()
  }
}

async function loadNodeState() {
  const configId = String(route.params.configId)
  if (!selectedNodeId.value) return
  const [preview, applied] = await Promise.all([
    api.wgPreview(configId, selectedNodeId.value),
    api.readAppliedConf(configId, selectedNodeId.value),
  ])
  previewContent.value = preview.content
  Object.assign(appliedState, applied)
}

async function saveApplied() {
  const configId = String(route.params.configId)
  if (!selectedNodeId.value) return
  try {
    await api.saveAppliedConf(configId, selectedNodeId.value, appliedState.content)
    await loadBase()
    ElMessage.success('同步态已保存')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '保存失败')
  }
}

async function syncNode() {
  const configId = String(route.params.configId)
  if (!selectedNodeId.value) return
  await api.syncNode(configId, selectedNodeId.value)
  await loadBase()
  ElMessage.success('节点已同步')
}

async function syncAll() {
  const configId = String(route.params.configId)
  await api.syncAll(configId)
  await loadBase()
  ElMessage.success('全部节点已同步')
}

function selectNode(value: string) {
  selectedNodeId.value = value
}

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
  await loadNodeState()
})

onMounted(async () => {
  try {
    await loadBase()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '应用页加载失败')
  }
})
</script>

<template>
  <div class="apply-page">
    <div class="apply-shell">
      <div class="apply-shell-header">
        <h2>{{ config?.name || '配置' }} - 配置应用</h2>
      </div>

      <div class="apply-shell-body">
        <div class="apply-sidebar content-band">
          <div class="apply-sidebar-header">
            <h3>节点列表</h3>
          </div>

          <div class="apply-sidebar-actions">
            <el-button size="small" type="primary" @click="syncAll">全部同步</el-button>
          </div>

          <div class="apply-node-menu">
            <el-menu :default-active="selectedNodeId" @select="selectNode">
              <el-menu-item v-for="node in nodes" :key="node.id" :index="node.id">
                {{ node.name }}
              </el-menu-item>
            </el-menu>
          </div>

          <div class="apply-config-toggle">
            <span>配置自动同步</span>
            <el-tag type="info">{{ config?.auto_sync ? '开启' : '关闭' }}</el-tag>
          </div>
        </div>

        <div class="apply-main">
          <div v-if="selectedSync" class="apply-node-bar content-band">
            <div class="apply-node-info">
              <span class="apply-node-name">{{ selectedSync.node_name }}</span>
              <span class="apply-status-badge">{{ selectedSync.status }}</span>
            </div>
            <div class="apply-node-actions">
              <span class="toggle-label-sm">节点自动同步：{{ selectedSync.auto_sync ? '开启' : '关闭' }}</span>
              <el-button size="small" type="primary" @click="syncNode">同步</el-button>
            </div>
          </div>

          <div v-if="selectedSync" class="apply-panels">
            <div class="apply-panel content-band">
              <div class="apply-panel-header">
                <span>系统态预览</span>
                <span class="panel-hint">只读</span>
              </div>
              <el-input :model-value="previewContent" type="textarea" :rows="24" readonly />
            </div>

            <div class="apply-panel content-band">
              <div class="apply-panel-header">
                <span>同步态配置</span>
                <div class="panel-actions">
                  <span class="panel-hint">系统态 {{ selectedSync.desired_version }} / 同步态 {{ selectedSync.staged_version }}</span>
                  <el-button size="small" type="primary" @click="saveApplied">保存修改</el-button>
                </div>
              </div>
              <el-input v-model="appliedState.content" type="textarea" :rows="24" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.apply-shell { display: grid; gap: 20px; }
.apply-shell-header h2 { margin: 0; color: #1f2d28; font-size: 28px; }
.apply-shell-body { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }
.apply-sidebar, .apply-main { display: grid; gap: 16px; }
.apply-sidebar-header h3, .apply-panel-header span:first-child { margin: 0; }
.apply-sidebar-actions { display: flex; }
.apply-config-toggle, .apply-node-bar, .apply-node-info, .apply-node-actions, .apply-panel-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.apply-node-name { font-weight: 700; color: #213029; }
.apply-status-badge { color: #0f8b8d; }
.apply-panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.panel-hint, .toggle-label-sm { color: #6c7e77; font-size: 12px; }
@media (max-width: 1100px) {
  .apply-shell-body { grid-template-columns: 1fr; }
  .apply-panels { grid-template-columns: 1fr; }
}
</style>
