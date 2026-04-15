<script setup lang="ts">
import { Check, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { SyncStatusRead } from '@/types/api'

const route = useRoute()

const syncStatus = shallowRef<SyncStatusRead | null>(null)
const previewContent = shallowRef('')
const appliedState = reactive({
  content: '',
  exists: false,
  node_name: '',
  node_type: '',
  desired_version: 0,
  staged_version: 0,
})

const currentNodeId = computed(() => String(route.params.nodeId))

async function loadNodeState() {
  const configId = String(route.params.configId)
  const nodeId = currentNodeId.value
  const [status, preview, applied] = await Promise.all([
    api.nodeSyncStatus(configId, nodeId),
    api.wgPreview(configId, nodeId),
    api.readAppliedConf(configId, nodeId),
  ])
  syncStatus.value = status
  previewContent.value = preview.content
  Object.assign(appliedState, applied)
}

async function saveApplied() {
  const configId = String(route.params.configId)
  try {
    await api.saveAppliedConf(configId, currentNodeId.value, appliedState.content)
    await loadNodeState()
    ElMessage.success('同步态已保存')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '保存失败')
  }
}

async function syncNode() {
  const configId = String(route.params.configId)
  await api.syncNode(configId, currentNodeId.value)
  await loadNodeState()
  ElMessage.success('已从系统态同步到同步态')
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    await loadNodeState()
  },
)

onMounted(async () => {
  try {
    await loadNodeState()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '配置应用加载失败')
  }
})
</script>

<template>
  <section class="node-template">
    <div v-if="syncStatus" class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>配置应用</h2>
          <p>默认同步配置表示从系统态同步到同步态。下发态属于客户端流程。</p>
        </div>
        <div class="template-toolbar__actions">
          <el-tag type="info">{{ syncStatus.status }}</el-tag>
          <el-button type="primary" :icon="Refresh" @click="syncNode">同步配置</el-button>
        </div>
      </div>

      <div class="version-strip">
        <span>系统态版本 {{ syncStatus.desired_version }}</span>
        <span>同步态版本 {{ syncStatus.staged_version }}</span>
      </div>

      <div class="apply-panels">
        <div class="apply-panel">
          <div class="apply-panel__header">
            <span>系统态</span>
            <span>只读</span>
          </div>
          <el-input :model-value="previewContent" type="textarea" :rows="24" readonly />
        </div>

        <div class="apply-panel">
          <div class="apply-panel__header">
            <span>同步态</span>
            <el-button size="small" type="primary" :icon="Check" @click="saveApplied">保存修改</el-button>
          </div>
          <el-input v-model="appliedState.content" type="textarea" :rows="24" />
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
.template-toolbar__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.version-strip { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; color: #60736c; }
.version-strip span { padding: 8px 12px; border: 1px solid #e0e8e4; border-radius: 8px; background: #f8fbf9; font-weight: 700; }
.apply-panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.apply-panel { display: grid; gap: 10px; min-width: 0; padding: 14px; border: 1px solid #e0e8e4; border-radius: 8px; background: #ffffff; box-shadow: 0 8px 20px rgba(42, 65, 58, 0.045); }
.apply-panel__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #213029; font-weight: 700; }
@media (max-width: 1100px) { .apply-panels { grid-template-columns: 1fr; } }
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } }
</style>
