<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigOverviewRead } from '@/types/api'

const route = useRoute()
const router = useRouter()
const overview = shallowRef<ConfigOverviewRead | null>(null)
const editVisible = shallowRef(false)

const editForm = reactive({
  name: '',
  description: '',
  enabled: true,
  virtual_subnet: '',
  default_listen_port: 51820,
  default_mtu: 1420 as number | null,
  default_dns: '' as string | null,
  auto_sync: true,
})

const nodes = computed(() => overview.value?.runtime_snapshot ?? [])

async function load() {
  overview.value = await api.configOverview(String(route.params.configId))
}

function fillEditForm() {
  if (!overview.value) return
  Object.assign(editForm, {
    name: overview.value.config.name,
    description: overview.value.config.description,
    enabled: overview.value.config.enabled,
    virtual_subnet: overview.value.config.virtual_subnet,
    default_listen_port: overview.value.config.default_listen_port,
    default_mtu: overview.value.config.default_mtu,
    default_dns: overview.value.config.default_dns,
    auto_sync: overview.value.config.auto_sync,
  })
}

function openEdit() {
  fillEditForm()
  editVisible.value = true
}

async function saveConfig() {
  try {
    await api.updateConfig(String(route.params.configId), { ...editForm })
    editVisible.value = false
    await load()
    ElMessage.success('配置已保存')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '配置保存失败')
  }
}

async function toggleEnabled(value: boolean) {
  if (!overview.value) return
  try {
    await api.updateConfig(String(route.params.configId), {
      ...overview.value.config,
      enabled: value,
    })
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '启用状态保存失败')
  }
}

async function deleteConfig() {
  if (!overview.value) return
  try {
    await ElMessageBox.confirm(`确定删除配置 ${overview.value.config.name} 吗？`, '删除配置', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.deleteConfig(String(route.params.configId))
    ElMessage.success('配置已删除')
    await router.push('/')
  } catch (error) {
    if (error instanceof Error || error instanceof ApiClientError) {
      ElMessage.error(error instanceof ApiClientError ? error.message : '配置删除失败')
    }
  }
}

function openNodePage() {
  void router.push(`/configs/${route.params.configId}/nodes`)
}

function openNodeTarget(section: 'mesh' | 'apply' | 'endpoints', nodeId: string) {
  void router.push({
    path: `/configs/${route.params.configId}/${section}`,
    query: { node: nodeId },
  })
}

watch(
  () => route.params.configId,
  async () => {
    await load()
  },
)

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '配置概览加载失败')
  }
})
</script>

<template>
  <div v-if="overview" class="config-overview">
    <div class="config-header-card">
      <div class="cfg-top-bar">
        <div class="cfg-name-group">
          <span class="cfg-name">{{ overview.config.name }}</span>
          <el-button size="small" text @click="openEdit">编辑</el-button>
        </div>
        <div class="cfg-actions">
          <el-switch
            :model-value="overview.config.enabled"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
            @change="(value: boolean | string | number) => toggleEnabled(Boolean(value))"
          />
          <el-button size="small" type="danger" plain @click="deleteConfig">删除</el-button>
        </div>
      </div>

      <div class="cfg-desc-row">
        <span class="cfg-desc">{{ overview.config.description || '未填写备注' }}</span>
      </div>

      <div class="cfg-props-grid">
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">虚拟网段</span>
          <span class="cfg-prop-value">{{ overview.config.virtual_subnet }}</span>
        </div>
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">默认监听端口</span>
          <span class="cfg-prop-value">{{ overview.config.default_listen_port }}</span>
        </div>
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">默认 MTU</span>
          <span class="cfg-prop-value">{{ overview.config.default_mtu || '未设置' }}</span>
        </div>
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">默认 DNS</span>
          <span class="cfg-prop-value">{{ overview.config.default_dns || '未设置' }}</span>
        </div>
      </div>
    </div>

    <div class="nodes-container content-band">
      <div class="nodes-header">
        <h3>Mesh 端点</h3>
        <div class="nodes-actions">
          <el-button size="small" @click="openNodePage">管理标签</el-button>
          <el-button size="small" type="primary" @click="openNodePage">新建端点</el-button>
        </div>
      </div>

      <div class="nodes-list-wrapper">
        <el-table :data="nodes" row-key="node_id">
          <el-table-column prop="node_name" label="名称" min-width="160" />
          <el-table-column prop="node_type" label="类型" width="100" />
          <el-table-column prop="peers_total" label="Peer 数" width="90" />
          <el-table-column label="在线" width="90">
            <template #default="{ row }">
              <el-tag :type="row.online ? 'success' : 'info'">{{ row.online ? '在线' : '离线' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="config_sync_state" label="同步状态" width="130" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-space>
                <el-button size="small" @click="openNodeTarget('mesh', row.node_id)">连接</el-button>
                <el-button size="small" @click="openNodeTarget('apply', row.node_id)">应用</el-button>
                <el-button size="small" type="primary" plain @click="openNodeTarget('endpoints', row.node_id)">控制</el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div class="placeholder-card content-band">
      <div class="placeholder">
        <div class="placeholder-icon">配置</div>
        <div class="placeholder-text">系统围绕配置文档生成、同步和下发而运行。</div>
      </div>
    </div>

    <el-dialog v-model="editVisible" title="编辑配置" width="560px">
      <el-form label-position="top">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" />
        </el-form-item>
        <el-form-item label="虚拟网段">
          <el-input v-model="editForm.virtual_subnet" />
        </el-form-item>
        <el-form-item label="默认监听端口">
          <el-input-number v-model="editForm.default_listen_port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认 MTU">
          <el-input-number v-model="editForm.default_mtu" :min="576" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认 DNS">
          <el-input v-model="editForm.default_dns" />
        </el-form-item>
        <el-switch v-model="editForm.auto_sync" active-text="自动同步" />
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.config-overview { display: grid; gap: 20px; }
.config-header-card { padding: 20px 22px; border: 1px solid #d8e1dd; border-radius: 8px; background: #fff; }
.cfg-top-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.cfg-name-group { display: flex; align-items: center; gap: 10px; }
.cfg-name { color: #1f2d28; font-size: 28px; font-weight: 700; line-height: 1.2; }
.cfg-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.cfg-desc-row { margin-top: 10px; }
.cfg-desc { color: #62766e; line-height: 1.6; }
.cfg-props-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.cfg-prop-item { display: grid; gap: 8px; padding: 14px; border: 1px solid #e0e8e4; border-radius: 8px; background: #f8fbf9; }
.cfg-prop-label { color: #73877f; font-size: 12px; }
.cfg-prop-value { color: #21302a; font-weight: 700; }
.nodes-container { padding: 20px; }
.nodes-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.nodes-header h3 { margin: 0; color: #213029; font-size: 20px; }
.nodes-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.placeholder-card { display: grid; place-items: center; min-height: 110px; }
.placeholder { display: grid; gap: 10px; text-align: center; }
.placeholder-icon { color: #0f8b8d; font-weight: 700; }
.placeholder-text { color: #667972; }
@media (max-width: 1100px) { .cfg-props-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) {
  .cfg-top-bar, .nodes-header { flex-direction: column; align-items: stretch; }
  .cfg-props-grid { grid-template-columns: 1fr; }
}
</style>
