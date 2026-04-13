<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead, MeshValidationRead, NodeRead, PeerLinkRead, WgPreviewRead } from '@/types/api'

const route = useRoute()
const router = useRouter()

const config = shallowRef<ConfigRead | null>(null)
const nodes = shallowRef<NodeRead[]>([])
const links = shallowRef<PeerLinkRead[]>([])
const selectedNodeId = shallowRef('')
const validation = shallowRef<MeshValidationRead | null>(null)
const preview = shallowRef<WgPreviewRead | null>(null)
const dialogVisible = shallowRef(false)

const form = reactive({
  local_node_id: '',
  peer_node_id: '',
  allowed_ips_forward: '',
  allowed_ips_reverse: '',
  persistent_keepalive: 25,
  endpoint_mode: 'auto',
  endpoint_ref_family: 'ipv4',
  endpoint_port_mode: 'ref_peer_listen_port',
  notes: '',
  enabled: true,
})

const selectedNode = computed(() => nodes.value.find((item) => item.id === selectedNodeId.value) ?? null)
const filteredLinks = computed(() => links.value.filter((item) => item.local_node_id === selectedNodeId.value))

async function load() {
  const configId = String(route.params.configId)
  const configs = await api.configs()
  config.value = configs.find((item) => item.id === configId) ?? null
  nodes.value = await api.nodes(configId)
  links.value = await api.peerLinks(configId)
  validation.value = await api.validateMesh(configId)
  const preferredNodeId = typeof route.query.node === 'string' ? route.query.node : ''
  selectedNodeId.value = preferredNodeId || selectedNodeId.value || nodes.value[0]?.id || ''
}

async function submit() {
  try {
    await api.createPeerLink(String(route.params.configId), form)
    dialogVisible.value = false
    await load()
    ElMessage.success('链路组已创建')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '链路创建失败')
  }
}

async function openPreview() {
  if (!selectedNodeId.value) return
  preview.value = await api.wgPreview(String(route.params.configId), selectedNodeId.value)
}

function selectNode(value: string) {
  selectedNodeId.value = value
}

watch(
  () => route.params.configId,
  async () => {
    selectedNodeId.value = ''
    await load()
  },
)

watch(selectedNodeId, async (value) => {
  if (!value) return
  await router.replace({ path: route.path, query: { node: value } })
})

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : 'Mesh 页面加载失败')
  }
})
</script>

<template>
  <div class="mesh-page">
    <div class="mesh-shell">
      <div class="mesh-shell-header">
        <h2>{{ config?.name || '配置' }} - Mesh 网络</h2>
      </div>

      <div class="mesh-shell-body">
        <div class="mesh-sidebar content-band">
          <div class="mesh-sidebar-header">
            <h3>端点列表</h3>
          </div>

          <div class="mesh-endpoint-menu">
            <el-menu :default-active="selectedNodeId" @select="selectNode">
              <el-menu-item v-for="node in nodes" :key="node.id" :index="node.id">
                {{ node.name }}
              </el-menu-item>
            </el-menu>
          </div>
        </div>

        <div class="mesh-main">
          <div class="mesh-info-card content-band">
            <template v-if="selectedNode">
              <h3>{{ selectedNode.name }}</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="类型">{{ selectedNode.node_type }}</el-descriptions-item>
                <el-descriptions-item label="虚拟 IP">{{ selectedNode.virtual_ip || '未设置' }}</el-descriptions-item>
                <el-descriptions-item label="公网端点">{{ selectedNode.ipv4_address || '未设置' }}</el-descriptions-item>
                <el-descriptions-item label="监听端口">{{ selectedNode.listen_port || '继承默认值' }}</el-descriptions-item>
              </el-descriptions>
            </template>
            <div v-else class="mesh-info-empty">请选择左侧端点查看详情</div>
          </div>

          <div class="mesh-feature-card content-band">
            <div class="mesh-feature-toolbar">
              <div class="mesh-toolbar-left">
                <el-button type="primary" size="small" :disabled="!selectedNodeId" @click="dialogVisible = true">新建连接</el-button>
                <el-button size="small" :disabled="!selectedNodeId" @click="openPreview">配置预览</el-button>
              </div>
              <el-tag v-if="validation" :type="validation.valid ? 'success' : 'warning'">
                {{ validation.valid ? '拓扑校验通过' : '拓扑校验有警告' }}
              </el-tag>
            </div>

            <div v-if="filteredLinks.length" class="mesh-connection-list">
              <el-table :data="filteredLinks" row-key="id">
                <el-table-column prop="direction" label="方向" width="90" />
                <el-table-column prop="allowed_ips" label="AllowedIPs" min-width="180" />
                <el-table-column prop="endpoint_mode" label="Endpoint 模式" width="130" />
                <el-table-column prop="notes" label="备注" min-width="180" />
              </el-table>
            </div>
            <div v-else class="mesh-main-placeholder">
              <div class="placeholder-title">连接区域预留</div>
              <div class="placeholder-desc">请选择左侧端点后创建连接卡片</div>
            </div>

            <div v-if="preview" class="mesh-preview">
              <pre class="preview-box">{{ preview.content }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="新建连接" width="560px">
      <el-form label-position="top">
        <el-form-item label="本地节点">
          <el-select v-model="form.local_node_id">
            <el-option v-for="node in nodes" :key="node.id" :value="node.id" :label="node.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="对端节点">
          <el-select v-model="form.peer_node_id">
            <el-option v-for="node in nodes" :key="node.id" :value="node.id" :label="node.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="正向 AllowedIPs">
          <el-input v-model="form.allowed_ips_forward" />
        </el-form-item>
        <el-form-item label="反向 AllowedIPs">
          <el-input v-model="form.allowed_ips_reverse" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mesh-shell { display: grid; gap: 20px; }
.mesh-shell-header h2 { margin: 0; color: #1f2d28; font-size: 28px; }
.mesh-shell-body { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }
.mesh-main { display: grid; gap: 20px; }
.mesh-sidebar-header, .mesh-feature-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.mesh-sidebar-header h3 { margin: 0; }
.mesh-info-empty, .mesh-main-placeholder { color: #667972; }
.placeholder-title { font-weight: 700; color: #213029; }
.placeholder-desc { margin-top: 6px; }
.preview-box { overflow: auto; padding: 16px; border: 1px solid #d8e1dd; border-radius: 8px; background: #f7fbf9; white-space: pre-wrap; }
.mesh-preview { margin-top: 16px; }
@media (max-width: 1100px) { .mesh-shell-body { grid-template-columns: 1fr; } }
</style>
