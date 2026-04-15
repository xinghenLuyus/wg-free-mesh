<script setup lang="ts">
import { Plus, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { MeshValidationRead, NodeRead, PeerLinkRead, WgPreviewRead } from '@/types/api'

const route = useRoute()

const nodes = shallowRef<NodeRead[]>([])
const links = shallowRef<PeerLinkRead[]>([])
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

const currentNodeId = computed(() => String(route.params.nodeId))
const currentNode = computed(() => nodes.value.find((item) => item.id === currentNodeId.value) ?? null)
const filteredLinks = computed(() => links.value.filter((item) => item.local_node_id === currentNodeId.value))
const peerOptions = computed(() => nodes.value.filter((item) => item.id !== currentNodeId.value))

async function load() {
  const configId = String(route.params.configId)
  nodes.value = await api.nodes(configId)
  links.value = await api.peerLinks(configId)
  validation.value = await api.validateMesh(configId)
  form.local_node_id = currentNodeId.value
}

function openCreate() {
  form.local_node_id = currentNodeId.value
  form.peer_node_id = peerOptions.value[0]?.id || ''
  dialogVisible.value = true
}

async function submit() {
  try {
    await api.createPeerLink(String(route.params.configId), form)
    dialogVisible.value = false
    await load()
    ElMessage.success('连接已创建')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '连接创建失败')
  }
}

async function openPreview() {
  preview.value = await api.wgPreview(String(route.params.configId), currentNodeId.value)
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    await load()
    preview.value = null
  },
)

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : 'Mesh 页面加载失败')
  }
})
</script>

<template>
  <section class="node-template">
    <div class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>Mesh 网络</h2>
          <p>管理当前节点的 Peer 连接关系。</p>
        </div>
        <div class="template-toolbar__actions">
          <el-button type="primary" :icon="Plus" @click="openCreate">新建连接</el-button>
          <el-button :icon="View" @click="openPreview">配置预览</el-button>
          <el-tag v-if="validation" :type="validation.valid ? 'success' : 'warning'">
            {{ validation.valid ? '拓扑校验通过' : '拓扑校验有警告' }}
          </el-tag>
        </div>
      </div>

      <el-table v-if="filteredLinks.length" :data="filteredLinks" row-key="id">
        <el-table-column prop="direction" label="方向" width="90" />
        <el-table-column prop="allowed_ips" label="AllowedIPs" min-width="180" />
        <el-table-column prop="endpoint_mode" label="Endpoint 模式" width="130" />
        <el-table-column prop="notes" label="备注" min-width="180" />
      </el-table>
      <div v-else class="empty-state">当前节点还没有连接。</div>

      <div v-if="preview" class="mesh-preview">
        <pre class="preview-box">{{ preview.content }}</pre>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="新建连接" width="560px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Plus /></el-icon></span>
        <div>
          <h3>建立 Peer 连接</h3>
          <p>连接关系只作用于当前节点和选定对端。</p>
        </div>
      </div>
      <el-form class="dialog-form" label-position="top">
        <el-form-item label="本地节点">
          <el-input :model-value="currentNode?.name || currentNodeId" disabled />
        </el-form-item>
        <el-form-item label="对端节点">
          <el-select v-model="form.peer_node_id" style="width: 100%">
            <el-option v-for="node in peerOptions" :key="node.id" :value="node.id" :label="node.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="正向 AllowedIPs"><el-input v-model="form.allowed_ips_forward" /></el-form-item>
        <el-form-item label="反向 AllowedIPs"><el-input v-model="form.allowed_ips_reverse" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.node-template { display: grid; gap: 20px; }
.template-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.template-toolbar h2 { margin: 0; color: var(--app-text); font-size: 22px; }
.template-toolbar p { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.template-toolbar__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.empty-state { display: grid; place-items: center; min-height: 170px; border: 1px dashed var(--app-border-strong); border-radius: 8px; background: rgba(255, 255, 255, 0.72); color: var(--app-muted); }
.mesh-preview { margin-top: 16px; }
.preview-box { overflow: auto; max-height: 520px; padding: 16px; border: 1px solid #d8e1dd; border-radius: 8px; background: #f7fbf9; color: #20302a; line-height: 1.55; white-space: pre-wrap; box-shadow: inset 0 1px 0 rgba(255,255,255,0.8); }
.dialog-intro { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; padding: 14px; border: 1px solid #e1ebe7; border-radius: 8px; background: #f8fbf9; }
.dialog-intro__icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 42px; height: 42px; border: 1px solid #bfe0da; border-radius: 8px; background: var(--app-primary-soft); color: var(--app-primary); }
.dialog-intro h3 { margin: 0; color: var(--app-text); }
.dialog-intro p { margin: 5px 0 0; color: var(--app-muted); line-height: 1.5; }
.dialog-form { display: grid; gap: 2px; }
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } }
</style>
