<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, shallowRef } from 'vue'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { HealthRead, SystemStatusRead } from '@/types/api'

const health = shallowRef<HealthRead | null>(null)
const status = shallowRef<SystemStatusRead | null>(null)

async function load() {
  health.value = await api.health()
  status.value = await api.systemStatus()
}

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '系统状态加载失败')
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
      <el-button @click="load">刷新</el-button>
    </div>
  </section>

  <section v-if="health" class="content-band section-gap">
    <el-descriptions :column="1" border title="健康检查">
      <el-descriptions-item label="状态">{{ health.status }}</el-descriptions-item>
      <el-descriptions-item label="服务">{{ health.service }}</el-descriptions-item>
      <el-descriptions-item label="版本">{{ health.version }}</el-descriptions-item>
      <el-descriptions-item label="时间">{{ health.timestamp }}</el-descriptions-item>
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
      <el-descriptions-item label="WireGuard">{{ status.services.wireguard }}</el-descriptions-item>
    </el-descriptions>
  </section>
</template>

<style scoped>
.content-card {
  padding: 20px 24px;
  border: 1px solid #d8e1dd;
  border-radius: 8px;
  background: #fff;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  margin: 0;
  color: #1f2d28;
  font-size: 28px;
}

.page-description {
  margin: 8px 0 0;
  color: #687871;
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
