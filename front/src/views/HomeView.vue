<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead } from '@/types/api'

const router = useRouter()

const configs = shallowRef<ConfigRead[]>([])
const dialogVisible = shallowRef(false)
const form = reactive({
  name: '',
  description: '',
  enabled: true,
  virtual_subnet: '10.66.0.0/24',
  default_listen_port: 51820,
  default_mtu: 1420,
  default_dns: '1.1.1.1',
  auto_sync: true,
})

async function load() {
  configs.value = await api.configs()
}

async function submit() {
  try {
    const config = await api.createConfig(form)
    dialogVisible.value = false
    await load()
    await router.push(`/configs/${config.id}`)
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '配置创建失败')
  }
}

async function openConfig(configId: string) {
  await router.push(`/configs/${configId}`)
}

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '配置加载失败')
  }
})
</script>

<template>
  <section class="content-card">
    <div class="page-header">
      <div>
        <h1 class="page-title">WireGuard 配置管理</h1>
        <p class="page-description">管理你的 WireGuard Mesh 网络配置</p>
      </div>
      <el-button type="primary" @click="dialogVisible = true">创建配置</el-button>
    </div>
  </section>

  <section class="config-grid">
    <button
      v-for="config in configs"
      :key="config.id"
      class="config-card"
      @click="openConfig(config.id)"
    >
      <div class="config-card__head">
        <h3>{{ config.name }}</h3>
        <el-tag :type="config.enabled ? 'success' : 'info'">{{ config.enabled ? '启用' : '停用' }}</el-tag>
      </div>
      <p class="config-card__desc">{{ config.description || '未填写备注' }}</p>
      <dl class="config-card__meta">
        <div>
          <dt>虚拟网段</dt>
          <dd>{{ config.virtual_subnet }}</dd>
        </div>
        <div>
          <dt>节点数</dt>
          <dd>{{ config.node_count }}</dd>
        </div>
        <div>
          <dt>动态节点</dt>
          <dd>{{ config.dynamic_node_count }}</dd>
        </div>
      </dl>
    </button>
    <div v-if="!configs.length" class="config-empty">
      <span>还没有配置，先创建第一份配置。</span>
    </div>
  </section>

  <el-dialog v-model="dialogVisible" title="创建配置" width="520px">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" />
      </el-form-item>
      <el-form-item label="虚拟子网">
        <el-input v-model="form.virtual_subnet" />
      </el-form-item>
      <el-form-item label="默认监听端口">
        <el-input-number v-model="form.default_listen_port" :min="1" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item label="默认 MTU">
        <el-input-number v-model="form.default_mtu" :min="576" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item label="默认 DNS">
        <el-input v-model="form.default_dns" />
      </el-form-item>
      <el-switch v-model="form.auto_sync" active-text="自动同步" />
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">创建</el-button>
    </template>
  </el-dialog>
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
  color: #1e2a25;
  font-size: 28px;
}

.page-description {
  margin: 8px 0 0;
  color: #687871;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.config-card {
  display: grid;
  gap: 14px;
  padding: 20px;
  border: 1px solid #d8e1dd;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.config-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.config-card__head h3 {
  margin: 0;
  color: #213029;
  font-size: 20px;
}

.config-card__desc {
  margin: 0;
  color: #62766e;
  line-height: 1.6;
}

.config-card__meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.config-card__meta dt {
  color: #7a8c85;
  font-size: 12px;
}

.config-card__meta dd {
  margin: 6px 0 0;
  color: #1f2d28;
  font-weight: 700;
}

.config-empty {
  display: grid;
  place-items: center;
  min-height: 160px;
  padding: 20px;
  border: 1px dashed #d8e1dd;
  border-radius: 8px;
  background: #fff;
  color: #6b7d76;
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
