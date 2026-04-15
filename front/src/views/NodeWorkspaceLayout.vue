<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, shallowRef, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead, EndpointStatusRead, NodeRead } from '@/types/api'

const route = useRoute()
const router = useRouter()

const config = shallowRef<ConfigRead | null>(null)
const node = shallowRef<NodeRead | null>(null)
const endpointStatus = shallowRef<EndpointStatusRead | null>(null)

const tabs = computed(() => {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  return [
    { label: 'Mesh 网络', path: `/configs/${configId}/nodes/${nodeId}/mesh` },
    { label: '配置应用', path: `/configs/${configId}/nodes/${nodeId}/apply` },
    { label: '端点控制', path: `/configs/${configId}/nodes/${nodeId}/control` },
  ]
})

async function load() {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  const [configs, nextNode, nextStatus] = await Promise.all([
    api.configs(),
    api.node(nodeId),
    api.endpointStatus(configId, nodeId),
  ])
  config.value = configs.find((item) => item.id === configId) ?? null
  node.value = nextNode
  endpointStatus.value = nextStatus
}

function goBack() {
  void router.push(`/configs/${route.params.configId}`)
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    await load()
  },
)

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '节点详情加载失败')
  }
})
</script>

<template>
  <div class="node-workspace">
    <div class="node-header-card">
      <div class="node-header-card__top">
        <el-button :icon="ArrowLeft" @click="goBack">返回配置</el-button>
        <span class="node-header-card__config">{{ config?.name || '配置' }}</span>
      </div>

      <div v-if="node" class="node-header-card__main">
        <div>
          <h1>{{ node.name }}</h1>
          <div class="node-header-card__tags">
            <el-tag type="info">{{ node.node_type }}</el-tag>
            <el-tag :type="endpointStatus?.runtime.online ? 'success' : 'info'">
              {{ endpointStatus?.runtime.online ? '在线' : '离线' }}
            </el-tag>
            <el-tag v-for="tag in node.tags" :key="tag" type="info">{{ tag }}</el-tag>
          </div>
        </div>
      </div>

      <div v-if="node" class="node-props-grid">
        <div class="node-prop-item">
          <span class="node-prop-label">虚拟 IP</span>
          <span class="node-prop-value">{{ node.virtual_ip || '未设置' }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">公网端点</span>
          <span class="node-prop-value">{{ node.ipv4_address || '未设置' }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">Peer 数</span>
          <span class="node-prop-value">{{ endpointStatus?.runtime.peers_total ?? 0 }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">WG 状态</span>
          <span class="node-prop-value">{{ endpointStatus?.runtime.wg_runtime_state || 'unknown' }}</span>
        </div>
      </div>

      <div class="node-tabs">
        <RouterLink
          v-for="tab in tabs"
          :key="tab.path"
          :to="tab.path"
          class="node-tab"
          :class="{ 'node-tab--active': route.path === tab.path }"
        >
          {{ tab.label }}
        </RouterLink>
      </div>
    </div>

    <RouterView />
  </div>
</template>

<style scoped>
.node-workspace { display: grid; gap: 20px; }
.node-header-card { padding: 22px; border: 1px solid var(--app-border); border-radius: 8px; background: linear-gradient(180deg, #ffffff 0%, #fbfdfc 100%); box-shadow: var(--app-shadow-md); }
.node-header-card__top { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.node-header-card__config { color: var(--app-muted); font-weight: 650; }
.node-header-card__main { display: flex; justify-content: space-between; gap: 16px; margin-top: 18px; }
.node-header-card__main h1 { margin: 0; color: var(--app-text); font-size: 30px; line-height: 1.2; }
.node-header-card__tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.node-props-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.node-prop-item { display: grid; gap: 8px; padding: 14px; border: 1px solid #e0e8e4; border-radius: 8px; background: #f8fbf9; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75); }
.node-prop-label { color: #73877f; font-size: 12px; font-weight: 650; }
.node-prop-value { color: #21302a; font-weight: 750; word-break: break-word; }
.node-tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; padding-top: 18px; border-top: 1px solid #e0e8e4; }
.node-tab { min-height: 40px; padding: 10px 16px; border: 1px solid #d8e1dd; border-radius: 8px; color: #4b5f58; background: #fff; text-decoration: none; font-weight: 700; transition: transform 160ms ease, border-color 160ms ease, background-color 160ms ease; }
.node-tab:hover { transform: translateY(-1px); border-color: #9bc8bf; background: #f7fbf9; }
.node-tab:focus-visible { outline: 0; box-shadow: var(--app-focus); }
.node-tab--active { color: #0f7375; border-color: #0f8b8d; background: #eef8f7; }
@media (max-width: 1100px) { .node-props-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) {
  .node-header-card__top, .node-header-card__main { flex-direction: column; align-items: stretch; }
  .node-props-grid { grid-template-columns: 1fr; }
}
</style>
