<script setup lang="ts">
import { ArrowLeft, Key, Plus } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead, NodeRead } from '@/types/api'
import { notify } from '@/utils/notify'

const route = useRoute()
const router = useRouter()

const config = shallowRef<ConfigRead | null>(null)
const nodes = shallowRef<NodeRead[]>([])
const dialogVisible = shallowRef(false)
const editingNodeId = shallowRef('')
const form = reactive({
  name: '',
  ipv4_address: '',
  ipv6_address: '',
  listen_port: 51820,
  virtual_ip: '',
  mtu: 1420,
  dns: '1.1.1.1',
  auto_sync: true,
  node_type: 'dynamic',
  public_key: '',
  private_key: '',
  tags: [] as string[],
})

const nodeCount = computed(() => nodes.value.length)
const dialogTitle = computed(() => (editingNodeId.value ? '编辑节点' : '新增节点'))

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? '静态节点' : '动态节点'
}

async function loadNodes() {
  const configId = String(route.params.configId)
  const configs = await api.configs()
  config.value = configs.find((item) => item.id === configId) ?? null
  nodes.value = await api.nodes(configId)
}

function resetForm() {
  editingNodeId.value = ''
  Object.assign(form, {
    name: '',
    ipv4_address: '',
    ipv6_address: '',
    listen_port: 51820,
    virtual_ip: '',
    mtu: 1420,
    dns: '1.1.1.1',
    auto_sync: true,
    node_type: 'dynamic',
    public_key: '',
    private_key: '',
    tags: [],
  })
}

async function openCreate() {
  resetForm()
  dialogVisible.value = true
  await autofillVirtualIp()
}

function openEdit(node: NodeRead) {
  editingNodeId.value = node.id
  Object.assign(form, {
    name: node.name,
    ipv4_address: node.ipv4_address || '',
    ipv6_address: node.ipv6_address || '',
    listen_port: node.listen_port || 51820,
    virtual_ip: node.virtual_ip || '',
    mtu: node.mtu || 1420,
    dns: node.dns || '',
    auto_sync: node.auto_sync,
    node_type: node.node_type,
    public_key: node.public_key,
    private_key: node.private_key,
    tags: [...node.tags],
  })
  dialogVisible.value = true
}

async function autofillKeys() {
  const keys = await api.generateKeys()
  form.private_key = keys.private_key
  form.public_key = keys.public_key
}

async function autofillVirtualIp() {
  const suggestion = await api.suggestIp(String(route.params.configId))
  form.virtual_ip = suggestion.ip
}

async function submit() {
  try {
    if (editingNodeId.value) {
      await api.updateNode(editingNodeId.value, form)
      notify.success('节点已保存')
    } else {
      await api.createNode(String(route.params.configId), form)
      notify.success('节点已创建')
    }
    dialogVisible.value = false
    await loadNodes()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '节点保存失败')
  }
}

async function deleteNode(node: NodeRead) {
  try {
    await ElMessageBox.confirm(`确定删除节点 ${node.name} 吗？`, '删除节点', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.deleteNode(node.id)
    await loadNodes()
    notify.success('节点已删除')
  } catch (error) {
    if (error instanceof ApiClientError) {
      notify.error(error.message)
    }
  }
}

function goTo(section: 'mesh' | 'apply' | 'control', nodeId: string) {
  void router.push(`/configs/${route.params.configId}/nodes/${nodeId}/${section}`)
}

watch(
  () => route.params.configId,
  async () => {
    await loadNodes()
  },
)

onMounted(async () => {
  try {
    await loadNodes()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '节点加载失败')
  }
})
</script>

<template>
  <section class="content-band">
    <div class="section-head">
      <div>
        <h3>{{ config?.name || '配置' }} - 节点管理</h3>
        <p class="section-subtitle">当前配置共 {{ nodeCount }} 个节点，节点仍然围绕配置详情工作流组织。</p>
      </div>
      <div class="section-actions">
        <el-button :icon="ArrowLeft" @click="router.push(`/configs/${route.params.configId}`)">返回概览</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增节点</el-button>
      </div>
    </div>

    <el-table :data="nodes" row-key="id">
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ nodeTypeLabel(row.node_type) }}</template>
      </el-table-column>
      <el-table-column prop="virtual_ip" label="虚拟 IP" min-width="140" />
      <el-table-column prop="ipv4_address" label="公网 IPv4" min-width="160" />
      <el-table-column prop="ipv6_address" label="公网 IPv6" min-width="160" />
      <el-table-column prop="listen_port" label="监听端口" width="100" />
      <el-table-column label="标签" min-width="140">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag v-for="tag in row.tags" :key="tag" type="info">{{ tag }}</el-tag>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320">
        <template #default="{ row }">
          <el-space>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="goTo('mesh', row.id)">Mesh</el-button>
            <el-button size="small" @click="goTo('apply', row.id)">应用</el-button>
            <el-button size="small" type="primary" plain @click="goTo('control', row.id)">控制</el-button>
            <el-button size="small" type="danger" plain @click="deleteNode(row)">删除</el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>
  </section>

  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="类型">
        <el-segmented
          v-model="form.node_type"
          :options="[
            { label: '动态节点', value: 'dynamic' },
            { label: '静态节点', value: 'static' },
          ]"
        />
      </el-form-item>
      <el-form-item label="公网 IPv4">
        <el-input v-model="form.ipv4_address" placeholder="可填写 IP 或域名" />
      </el-form-item>
      <el-form-item label="公网 IPv6">
        <el-input v-model="form.ipv6_address" placeholder="可填写 IP 或域名" />
      </el-form-item>
      <el-form-item label="监听端口">
        <el-input-number v-model="form.listen_port" :min="1" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item label="虚拟 IP">
        <el-input v-model="form.virtual_ip">
          <template #append>
            <el-button @click="autofillVirtualIp">推荐</el-button>
          </template>
        </el-input>
      </el-form-item>
      <el-form-item label="私钥">
        <el-input v-model="form.private_key" type="textarea" />
      </el-form-item>
      <el-form-item label="公钥">
        <el-input v-model="form.public_key" type="textarea" />
      </el-form-item>
      <el-button plain :icon="Key" @click="autofillKeys">生成密钥</el-button>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-head h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 22px;
}

.section-subtitle {
  margin: 8px 0 0;
  color: var(--app-muted);
  line-height: 1.6;
}

.section-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 860px) {
  .section-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
