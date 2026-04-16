<script setup lang="ts">
import { ArrowLeft, Delete, Key, Setting } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigRead, EndpointStatusRead, NodeRead, NodeWorkspaceUpdatedPayload, RealtimeEvent, TagRead } from '@/types/api'
import { normalizeTags, toNodeUpdatePayload } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'

const route = useRoute()
const router = useRouter()

const config = shallowRef<ConfigRead | null>(null)
const node = shallowRef<NodeRead | null>(null)
const configTags = shallowRef<TagRead[]>([])
const endpointStatus = shallowRef<EndpointStatusRead | null>(null)
const settingsVisible = shallowRef(false)
const loading = shallowRef(false)
const loadError = shallowRef('')
let loadTicket = 0
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'node.workspace.updated') return
  const payload = event.payload as unknown as NodeWorkspaceUpdatedPayload
  if (payload.config_id !== String(route.params.configId) || payload.node_id !== String(route.params.nodeId)) return
  config.value = payload.workspace.config
  node.value = payload.workspace.node
  endpointStatus.value = payload.workspace.endpoint_status
  configTags.value = payload.workspace.tags
})

const settingsForm = reactive({
  name: '',
  ipv4_address: '',
  ipv6_address: '',
  listen_port: null as number | null,
  virtual_ip: '',
  mtu: null as number | null,
  dns: '',
  auto_sync: true,
  node_type: 'dynamic' as NodeRead['node_type'],
  public_key: '',
  private_key: '',
  tags: [] as string[],
})

const tabs = computed(() => {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  return [
    { label: 'Mesh 网络', path: `/configs/${configId}/nodes/${nodeId}/mesh` },
    { label: '配置预览', path: `/configs/${configId}/nodes/${nodeId}/apply` },
    { label: '端点控制', path: `/configs/${configId}/nodes/${nodeId}/control` },
  ]
})

const allTags = computed(() => configTags.value.map((item) => item.name))

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? '静态节点' : '动态节点'
}

async function load() {
  const ticket = ++loadTicket
  loading.value = true
  loadError.value = ''
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  try {
    const [configs, nextNode, nextStatus, nextTags] = await Promise.all([
      api.configs(),
      api.node(nodeId),
      api.endpointStatus(configId, nodeId),
      api.tags(configId),
    ])
    if (ticket !== loadTicket) return
    config.value = configs.find((item) => item.id === configId) ?? null
    node.value = nextNode
    endpointStatus.value = nextStatus
    configTags.value = nextTags
  } catch (error) {
    if (ticket !== loadTicket) return
    loadError.value = error instanceof ApiClientError ? error.message : '节点详情加载失败'
    throw error
  } finally {
    if (ticket === loadTicket) loading.value = false
  }
}

function goBack() {
  void router.push(`/configs/${route.params.configId}`)
}

function fillSettingsForm() {
  if (!node.value) return
  Object.assign(settingsForm, {
    name: node.value.name,
    ipv4_address: node.value.ipv4_address || '',
    ipv6_address: node.value.ipv6_address || '',
    listen_port: node.value.listen_port,
    virtual_ip: node.value.virtual_ip || '',
    mtu: node.value.mtu,
    dns: node.value.dns || '',
    auto_sync: node.value.auto_sync,
    node_type: node.value.node_type,
    public_key: node.value.public_key,
    private_key: node.value.private_key,
    tags: [...node.value.tags],
  })
}

function openSettings() {
  fillSettingsForm()
  settingsVisible.value = true
}

async function autofillKeys() {
  try {
    const keys = await api.generateKeys()
    settingsForm.private_key = keys.private_key
    settingsForm.public_key = keys.public_key
    notify.success('密钥已生成')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '密钥生成失败')
  }
}

async function saveNodeSettings() {
  if (!node.value) return
  try {
    await api.updateNode(node.value.id, toNodeUpdatePayload(node.value, {
      name: settingsForm.name,
      ipv4_address: settingsForm.ipv4_address || null,
      ipv6_address: settingsForm.ipv6_address || null,
      listen_port: settingsForm.listen_port,
      virtual_ip: settingsForm.virtual_ip || null,
      mtu: settingsForm.mtu,
      dns: settingsForm.dns || null,
      auto_sync: settingsForm.auto_sync,
      node_type: settingsForm.node_type,
      public_key: settingsForm.public_key,
      private_key: settingsForm.private_key,
    }))
    await api.replaceNodeTags(node.value.id, normalizeTags(settingsForm.tags))
    settingsVisible.value = false
    await load()
    notify.success('端点设置已保存')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '端点设置保存失败')
  }
}

async function deleteNodeFromSettings() {
  if (!node.value) return
  try {
    await ElMessageBox.confirm(
      `删除端点后，${node.value.name} 的节点信息、Mesh 连接和同步态配置都会一起移除。`,
      '删除端点',
      {
        type: 'warning',
        confirmButtonText: '删除端点',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
    const configId = node.value.config_id
    await api.deleteNode(node.value.id)
    settingsVisible.value = false
    notify.success('端点已删除')
    await router.push(`/configs/${configId}`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    notify.error(error instanceof ApiClientError ? error.message : '端点删除失败')
  }
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    try {
      await load()
    } catch {
      notify.error(loadError.value || '节点详情加载失败')
    }
  },
)

onMounted(async () => {
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '节点详情加载失败')
  }
})
</script>

<template>
  <div class="node-workspace">
    <div class="node-header-card">
      <div class="node-header-card__top">
        <el-button :icon="ArrowLeft" @click="goBack">返回配置</el-button>
        <div class="node-header-card__actions">
          <span class="node-header-card__config">{{ config?.name || '配置' }}</span>
          <el-button v-if="node" type="primary" plain :icon="Setting" @click="openSettings">端点设置</el-button>
        </div>
      </div>

      <div v-if="node" class="node-header-card__main">
        <div>
          <h1>{{ node.name }}</h1>
          <div class="node-header-card__tags">
            <el-tag type="info">{{ nodeTypeLabel(node.node_type) }}</el-tag>
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
          <span class="node-prop-label">公网 IPv4</span>
          <span class="node-prop-value">{{ node.ipv4_address || '未设置' }}</span>
        </div>
        <div class="node-prop-item">
          <span class="node-prop-label">公网 IPv6</span>
          <span class="node-prop-value">{{ node.ipv6_address || '未设置' }}</span>
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

    <RouterView v-slot="{ Component, route: viewRoute }">
      <Transition name="route-template" appear>
        <component :is="Component" :key="viewRoute.fullPath" />
      </Transition>
    </RouterView>

    <div v-if="loading && !node" class="view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !node" class="view-feedback view-feedback--error">{{ loadError }}</div>

    <el-dialog v-model="settingsVisible" title="端点设置" width="640px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Setting /></el-icon></span>
        <div>
          <h3>端点基础信息</h3>
          <p>编辑端点地址、虚拟 IP、密钥和所属标签。保存后会更新系统态配置。</p>
        </div>
      </div>

      <el-form class="dialog-form" label-position="top">
        <el-form-item label="名称">
          <el-input v-model="settingsForm.name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-segmented
            v-model="settingsForm.node_type"
            :options="[
              { label: '动态节点', value: 'dynamic' },
              { label: '静态节点', value: 'static' },
            ]"
          />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="公网 IPv4">
            <el-input v-model="settingsForm.ipv4_address" placeholder="可填写 IP 或域名" />
          </el-form-item>
          <el-form-item label="公网 IPv6">
            <el-input v-model="settingsForm.ipv6_address" placeholder="可填写 IP 或域名" />
          </el-form-item>
          <el-form-item label="监听端口">
            <el-input-number v-model="settingsForm.listen_port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item label="虚拟 IP">
            <el-input v-model="settingsForm.virtual_ip" />
          </el-form-item>
          <el-form-item label="MTU">
            <el-input-number v-model="settingsForm.mtu" :min="576" :max="65535" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item label="DNS">
          <el-input v-model="settingsForm.dns" />
        </el-form-item>
        <el-form-item label="所属标签">
          <el-select
            v-model="settingsForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入标签"
            style="width: 100%"
          >
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
        <div class="switch-row">
          <div>
            <strong>自动同步</strong>
            <span>系统态生成后自动同步到同步态。</span>
          </div>
          <el-switch v-model="settingsForm.auto_sync" />
        </div>
        <el-form-item label="私钥">
          <el-input v-model="settingsForm.private_key" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="公钥">
          <el-input v-model="settingsForm.public_key" type="textarea" :rows="3" />
        </el-form-item>
        <el-button plain :icon="Key" @click="autofillKeys">生成密钥</el-button>
      </el-form>

      <template #footer>
        <el-button type="danger" plain :icon="Delete" @click="deleteNodeFromSettings">删除端点</el-button>
        <el-button @click="settingsVisible = false">取消</el-button>
        <el-button type="primary" @click="saveNodeSettings">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.node-workspace { display: grid; gap: 20px; }
.node-header-card { padding: 22px; border: 1px solid var(--app-border); border-radius: 8px; background: linear-gradient(180deg, #ffffff 0%, #fbfdfc 100%); box-shadow: var(--app-shadow-md); }
.node-header-card__top { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.node-header-card__actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 10px; }
.node-header-card__config { color: var(--app-muted); font-weight: 650; }
.node-header-card__main { display: flex; justify-content: space-between; gap: 16px; margin-top: 18px; }
.node-header-card__main h1 { margin: 0; color: var(--app-text); font-size: 30px; line-height: 1.2; }
.node-header-card__tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.node-props-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.node-prop-item { display: grid; gap: 8px; padding: 14px; border: 1px solid #e0e8e4; border-radius: 8px; background: #f8fbf9; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75); }
.node-prop-label { color: #73877f; font-size: 12px; font-weight: 650; }
.node-prop-value { color: #21302a; font-weight: 750; word-break: break-word; }
.node-tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; padding-top: 18px; border-top: 1px solid #e0e8e4; }
.node-tab { min-height: 40px; padding: 10px 16px; border: 1px solid #d8e1dd; border-radius: 8px; color: #4b5f58; background: #fff; text-decoration: none; font-weight: 700; transition: transform 160ms ease, border-color 160ms ease, background-color 160ms ease; }
.node-tab:hover { transform: translateY(-1px); border-color: #9bc8bf; background: #f7fbf9; }
.node-tab:focus-visible { outline: 0; box-shadow: var(--app-focus); }
.node-tab--active { color: #0f7375; border-color: #0f8b8d; background: #eef8f7; }
.view-feedback { padding: 18px 20px; border: 1px solid #d8e1dd; border-radius: 8px; background: #f8fbf9; color: #556a62; box-shadow: var(--app-shadow-sm); }
.view-feedback--silent { min-height: 88px; background: transparent; border-color: transparent; box-shadow: none; }
.view-feedback--error { border-color: #f0d4d4; background: #fff7f7; color: #9a4b4b; }
.dialog-intro { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; padding: 14px; border: 1px solid #e1ebe7; border-radius: 8px; background: #f8fbf9; }
.dialog-intro__icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 42px; height: 42px; border: 1px solid #bfe0da; border-radius: 8px; background: var(--app-primary-soft); color: var(--app-primary); }
.dialog-intro h3 { margin: 0; color: var(--app-text); }
.dialog-intro p { margin: 5px 0 0; color: var(--app-muted); line-height: 1.5; }
.dialog-form { display: grid; gap: 2px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px; border: 1px solid #e1ebe7; border-radius: 8px; background: #fbfcfb; }
.switch-row strong, .switch-row span { display: block; }
.switch-row strong { color: var(--app-text); }
.switch-row span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
@media (max-width: 1100px) { .node-props-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) {
  .node-header-card__top, .node-header-card__main, .switch-row { flex-direction: column; align-items: stretch; }
  .node-header-card__actions { justify-content: flex-start; }
  .node-props-grid, .form-grid { grid-template-columns: 1fr; }
}
</style>
