<script setup lang="ts">
import { CollectionTag, Key, Plus, Setting } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigOverviewNodeCardRead, ConfigOverviewRead, ConfigOverviewUpdatedPayload, NodeRead, RealtimeEvent, TagRead } from '@/types/api'
import { normalizeTags } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'

type ViewMode = 'grid' | 'list'
type SortKey = 'name' | 'virtual_ip' | 'created_at' | 'online' | 'node_type'

const route = useRoute()
const router = useRouter()
const overview = shallowRef<ConfigOverviewRead | null>(null)
const fullNodes = shallowRef<NodeRead[]>([])
const tags = shallowRef<TagRead[]>([])
const settingsVisible = shallowRef(false)
const createVisible = shallowRef(false)
const tagVisible = shallowRef(false)
const viewMode = shallowRef<ViewMode>('grid')
const sortKey = shallowRef<SortKey>('name')
const tagFilter = shallowRef('')
const tagSearch = shallowRef('')
const newTagName = shallowRef('')
const selectedTagForAssignment = shallowRef('')
const selectedNodeIds = shallowRef<string[]>([])
const loading = shallowRef(false)
const loadError = shallowRef('')
let loadTicket = 0
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'config.overview.updated') return
  const payload = event.payload as unknown as ConfigOverviewUpdatedPayload
  if (payload.config_id !== String(route.params.configId)) return
  overview.value = payload.overview
  fullNodes.value = payload.overview.nodes
  tags.value = payload.tags
})

const settingsForm = reactive({
  name: '',
  description: '',
  enabled: true,
  virtual_subnet: '',
  default_listen_port: 51820,
  default_mtu: 1420 as number | null,
  default_dns: '' as string | null,
  auto_sync: true,
})

const createForm = reactive({
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
  tags_text: '',
})

const nodeCards = computed(() => overview.value?.node_cards ?? [])

const tagUsages = computed(() => tags.value)

const allTags = computed(() => tags.value.map((tag) => tag.name))

const visibleTagUsages = computed(() => {
  const keyword = tagSearch.value.trim().toLowerCase()
  if (!keyword) return tagUsages.value
  return tagUsages.value.filter((tag) => tag.name.toLowerCase().includes(keyword))
})

const visibleNodes = computed(() => {
  const filtered = tagFilter.value
    ? nodeCards.value.filter((node) => node.tags.includes(tagFilter.value))
    : nodeCards.value

  return [...filtered].sort((left: ConfigOverviewNodeCardRead, right: ConfigOverviewNodeCardRead) => {
    if (sortKey.value === 'online') return Number(right.online) - Number(left.online)
    if (sortKey.value === 'created_at') return right.created_at.localeCompare(left.created_at)
    const leftValue = String(left[sortKey.value] ?? '')
    const rightValue = String(right[sortKey.value] ?? '')
    return leftValue.localeCompare(rightValue)
  })
})

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? '静态节点' : '动态节点'
}

const assignableTagOptions = computed(() => {
  const createdTag = newTagName.value.trim()
  return normalizeTags([...allTags.value, ...(createdTag ? [createdTag] : [])])
})

async function load() {
  const ticket = ++loadTicket
  loading.value = true
  loadError.value = ''
  const configId = String(route.params.configId)
  try {
    const [nextOverview, nextTags] = await Promise.all([
      api.configOverview(configId),
      api.tags(configId),
    ])
    if (ticket !== loadTicket) return
    overview.value = nextOverview
    fullNodes.value = nextOverview.nodes
    tags.value = nextTags
  } catch (error) {
    if (ticket !== loadTicket) return
    loadError.value = error instanceof ApiClientError ? error.message : '配置概览加载失败'
    throw error
  } finally {
    if (ticket === loadTicket) loading.value = false
  }
}

function fillSettingsForm() {
  if (!overview.value) return
  Object.assign(settingsForm, {
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

function resetCreateForm() {
  Object.assign(createForm, {
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
    tags_text: '',
  })
}

function openSettings() {
  fillSettingsForm()
  settingsVisible.value = true
}

async function openCreate() {
  resetCreateForm()
  createVisible.value = true
  try {
    const suggestion = await api.suggestIp(String(route.params.configId))
    createForm.virtual_ip = suggestion.ip
  } catch {
    // 推荐失败不阻断手动填写。
  }
}

function openTagManager() {
  tagSearch.value = ''
  newTagName.value = ''
  selectedTagForAssignment.value = tagFilter.value || allTags.value[0] || ''
  selectedNodeIds.value = []
  tagVisible.value = true
}

function applyTagFilter(tag: string) {
  tagFilter.value = tag
  tagVisible.value = false
}

function clearTagFilter() {
  tagFilter.value = ''
}

async function createTag() {
  const tag = newTagName.value.trim()
  if (!tag) {
    notify.warning('请输入标签名称')
    return
  }
  try {
    const createdTag = await api.createTag(String(route.params.configId), tag)
    selectedTagForAssignment.value = createdTag.name
    newTagName.value = ''
    await load()
    notify.success('标签已创建，请选择端点应用')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '标签创建失败')
  }
}

async function applySelectedTagToNodes() {
  const tag = selectedTagForAssignment.value.trim()
  if (!tag) {
    notify.warning('请选择或创建标签')
    return
  }
  if (!selectedNodeIds.value.length) {
    notify.warning('请选择需要添加标签的端点')
    return
  }

  try {
    await api.applyTagToNodes(String(route.params.configId), tag, selectedNodeIds.value)
    await load()
    selectedNodeIds.value = []
    selectedTagForAssignment.value = tag
    notify.success('标签已应用到选中的端点')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '标签应用失败')
  }
}

async function removeTagFromNode(node: NodeRead, tag: string) {
  try {
    await api.removeTagFromNode(node.id, tag)
    await load()
    notify.success('已移除端点标签')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '标签移除失败')
  }
}

async function deleteTag(tag: string) {
  try {
    await ElMessageBox.confirm(`确定从所有端点删除标签 ${tag} 吗？`, '删除标签', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.deleteTag(String(route.params.configId), tag)
    if (tagFilter.value === tag) clearTagFilter()
    if (selectedTagForAssignment.value === tag) selectedTagForAssignment.value = ''
    await load()
    notify.success('标签已删除')
  } catch (error) {
    if (error instanceof ApiClientError) {
      notify.error(error.message)
    }
  }
}

async function saveSettings() {
  try {
    await api.updateConfig(String(route.params.configId), { ...settingsForm })
    settingsVisible.value = false
    await load()
    notify.success('配置已保存')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '配置保存失败')
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
    notify.success('配置已删除')
    settingsVisible.value = false
    await router.push('/')
  } catch (error) {
    if (error instanceof ApiClientError) {
      notify.error(error.message)
    }
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
    notify.error(error instanceof ApiClientError ? error.message : '启用状态保存失败')
  }
}

async function autofillKeys() {
  const keys = await api.generateKeys()
  createForm.private_key = keys.private_key
  createForm.public_key = keys.public_key
}

async function autofillVirtualIp() {
  const suggestion = await api.suggestIp(String(route.params.configId))
  createForm.virtual_ip = suggestion.ip
}

async function createNode() {
  const tags = createForm.tags_text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  try {
    await api.createNode(String(route.params.configId), {
      name: createForm.name,
      ipv4_address: createForm.ipv4_address,
      ipv6_address: createForm.ipv6_address,
      listen_port: createForm.listen_port,
      virtual_ip: createForm.virtual_ip,
      mtu: createForm.mtu,
      dns: createForm.dns,
      auto_sync: createForm.auto_sync,
      node_type: createForm.node_type,
      public_key: createForm.public_key,
      private_key: createForm.private_key,
      tags,
    })
    createVisible.value = false
    await load()
    notify.success('端点已创建')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '端点创建失败')
  }
}

function openNode(nodeId: string) {
  void router.push(`/configs/${route.params.configId}/nodes/${nodeId}`)
}

watch(
  () => route.params.configId,
  async () => {
    try {
      await load()
    } catch {
      notify.error(loadError.value || '配置概览加载失败')
    }
  },
)

onMounted(async () => {
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '配置概览加载失败')
  }
})
</script>

<template>
  <div class="config-overview">
    <div v-if="loading && !overview" class="view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !overview" class="view-feedback view-feedback--error">{{ loadError }}</div>
    <template v-else-if="overview">
    <div class="config-header-card">
      <div class="cfg-top-bar">
        <div class="cfg-name-group">
          <span class="cfg-name">{{ overview.config.name }}</span>
        </div>
        <div class="cfg-actions">
          <el-switch
            :model-value="overview.config.enabled"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
            @change="(value: boolean | string | number) => toggleEnabled(Boolean(value))"
          />
          <el-button size="small" type="primary" plain :icon="Setting" @click="openSettings">设置</el-button>
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

      <div class="node-toolbar">
        <div class="node-toolbar__actions">
          <el-button class="soft-action" :icon="CollectionTag" @click="openTagManager">标签管理</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新建端点</el-button>
        </div>
        <div class="node-toolbar__filters">
          <el-select v-model="sortKey" style="width: 140px">
            <el-option label="按名称" value="name" />
            <el-option label="按虚拟 IP" value="virtual_ip" />
            <el-option label="按创建时间" value="created_at" />
            <el-option label="按在线状态" value="online" />
            <el-option label="按节点类型" value="node_type" />
          </el-select>
          <el-select v-model="tagFilter" clearable placeholder="按标签筛选" style="width: 160px">
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
          <el-segmented v-model="viewMode" :options="[
            { label: '网格', value: 'grid' },
            { label: '列表', value: 'list' },
          ]" />
        </div>
      </div>
    </div>

    <section class="nodes-section">
      <div v-if="viewMode === 'grid'" class="node-grid">
        <button
          v-for="node in visibleNodes"
          :key="node.id"
          class="node-card"
          @click="openNode(node.id)"
        >
          <div class="node-card__head">
            <h3>{{ node.name }}</h3>
            <el-tag :type="node.online ? 'success' : 'info'">{{ node.online ? '在线' : '离线' }}</el-tag>
          </div>
          <dl class="node-card__meta">
            <div>
              <dt>类型</dt>
              <dd>{{ nodeTypeLabel(node.node_type) }}</dd>
            </div>
            <div>
              <dt>虚拟 IP</dt>
              <dd>{{ node.virtual_ip || '未设置' }}</dd>
            </div>
            <div>
              <dt>公网 IPv4</dt>
              <dd>{{ node.ipv4_address || '未设置' }}</dd>
            </div>
            <div>
              <dt>公网 IPv6</dt>
              <dd>{{ node.ipv6_address || '未设置' }}</dd>
            </div>
          </dl>
          <div class="node-card__tags">
            <el-tag v-for="tag in node.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
            <span v-if="!node.tags.length" class="node-card__empty">无标签</span>
          </div>
        </button>
      </div>

      <div v-else class="node-strip-grid">
        <button
          v-for="node in visibleNodes"
          :key="node.id"
          class="node-strip-card"
          @click="openNode(node.id)"
        >
          <div class="node-strip-card__main">
            <div class="node-strip-card__title">
              <h3>{{ node.name }}</h3>
              <el-tag :type="node.online ? 'success' : 'info'" size="small">{{ node.online ? '在线' : '离线' }}</el-tag>
            </div>
            <div class="node-strip-card__tags">
              <el-tag v-for="tag in node.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
              <span v-if="!node.tags.length" class="node-card__empty">无标签</span>
            </div>
          </div>
          <div class="node-strip-card__facts">
            <span>{{ nodeTypeLabel(node.node_type) }}</span>
            <span>{{ node.virtual_ip || '未设置虚拟 IP' }}</span>
            <span>IPv4 {{ node.ipv4_address || '未设置' }}</span>
            <span>IPv6 {{ node.ipv6_address || '未设置' }}</span>
            <span>Peer {{ node.peers_total }}</span>
          </div>
        </button>
      </div>
    </section>

    <el-dialog v-model="settingsVisible" title="配置设置" width="560px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Setting /></el-icon></span>
        <div>
          <h3>配置基础信息</h3>
          <p>这些字段用于生成系统态配置，并可自动同步到同步态。</p>
        </div>
      </div>
      <el-form class="dialog-form" label-position="top">
        <el-form-item label="名称"><el-input v-model="settingsForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="settingsForm.description" type="textarea" :rows="3" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="虚拟网段"><el-input v-model="settingsForm.virtual_subnet" /></el-form-item>
          <el-form-item label="默认监听端口">
            <el-input-number v-model="settingsForm.default_listen_port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item label="默认 MTU">
            <el-input-number v-model="settingsForm.default_mtu" :min="576" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item label="默认 DNS"><el-input v-model="settingsForm.default_dns" /></el-form-item>
        </div>
        <div class="switch-row">
          <div>
            <strong>自动同步</strong>
            <span>系统态生成后自动同步到同步态。</span>
          </div>
          <el-switch v-model="settingsForm.auto_sync" />
        </div>
      </el-form>
      <div class="settings-danger-zone">
        <div>
          <div class="settings-danger-zone__title">删除配置</div>
          <div class="settings-danger-zone__desc">删除后会移除该配置及其节点、连接和同步状态。</div>
        </div>
        <el-button type="danger" plain @click="deleteConfig">删除配置</el-button>
      </div>
      <template #footer>
        <el-button @click="settingsVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSettings">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="新建端点" width="560px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Plus /></el-icon></span>
        <div>
          <h3>端点接入</h3>
          <p>端点创建后会出现在当前配置的节点网格中。</p>
        </div>
      </div>
      <el-form class="dialog-form" label-position="top">
        <el-form-item label="名称"><el-input v-model="createForm.name" placeholder="例如：office-gateway" /></el-form-item>
        <el-form-item label="类型">
          <el-segmented
            v-model="createForm.node_type"
            :options="[
              { label: '动态节点', value: 'dynamic' },
              { label: '静态节点', value: 'static' },
            ]"
          />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="公网 IPv4"><el-input v-model="createForm.ipv4_address" placeholder="可填写 IP 或域名" /></el-form-item>
          <el-form-item label="公网 IPv6"><el-input v-model="createForm.ipv6_address" placeholder="可填写 IP 或域名" /></el-form-item>
          <el-form-item label="虚拟 IP">
            <el-input v-model="createForm.virtual_ip">
              <template #append><el-button @click="autofillVirtualIp">推荐</el-button></template>
            </el-input>
          </el-form-item>
        </div>
        <el-form-item label="标签">
          <el-input v-model="createForm.tags_text" placeholder="多个标签用英文逗号分隔" />
        </el-form-item>
        <el-form-item label="私钥"><el-input v-model="createForm.private_key" type="textarea" /></el-form-item>
        <el-form-item label="公钥"><el-input v-model="createForm.public_key" type="textarea" /></el-form-item>
        <el-button plain :icon="Key" @click="autofillKeys">生成密钥</el-button>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="createNode">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tagVisible" title="标签管理" width="760px">
      <div class="tag-manager">
        <div class="tag-manager__hero">
          <div>
            <h3>标签</h3>
            <p>标签来自端点配置。可以创建标签、按标签筛选，也可以选择端点批量应用标签。</p>
          </div>
          <el-button v-if="tagFilter" @click="clearTagFilter">清除筛选</el-button>
        </div>

        <div class="tag-create-panel">
          <el-input v-model="newTagName" placeholder="新标签名称" clearable @keyup.enter="createTag" />
          <el-button type="primary" :icon="Plus" @click="createTag">创建标签</el-button>
        </div>

        <div class="tag-manager__split">
          <section class="tag-manager__section">
            <div class="tag-manager__section-head">
              <h4>标签列表</h4>
              <el-input v-model="tagSearch" placeholder="搜索标签" clearable />
            </div>
            <div class="tag-manager__grid">
              <div
                v-for="tag in visibleTagUsages"
                :key="tag.name"
                class="tag-card"
                :class="{ 'tag-card--active': tagFilter === tag.name }"
              >
                <button class="tag-card__body" @click="applyTagFilter(tag.name)">
                  <span class="tag-card__name">{{ tag.name }}</span>
                  <span class="tag-card__count">{{ tag.count }} 个端点</span>
                </button>
                <el-button size="small" type="danger" plain @click="deleteTag(tag.name)">删除</el-button>
              </div>
              <div v-if="!visibleTagUsages.length" class="tag-manager__empty">暂无匹配标签</div>
            </div>
          </section>

          <section class="tag-manager__section">
            <div class="tag-manager__section-head">
              <h4>端点标签</h4>
              <el-select v-model="selectedTagForAssignment" placeholder="选择标签" style="width: 100%">
                <el-option v-for="tag in assignableTagOptions" :key="tag" :label="tag" :value="tag" />
              </el-select>
            </div>

            <el-select
              v-model="selectedNodeIds"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择要添加标签的端点"
              style="width: 100%"
            >
              <el-option v-for="node in fullNodes" :key="node.id" :label="node.name" :value="node.id" />
            </el-select>
            <el-button type="primary" class="tag-assign-button" @click="applySelectedTagToNodes">应用到端点</el-button>

            <div class="tag-node-list">
              <div v-for="node in fullNodes" :key="node.id" class="tag-node-card">
                <div>
                  <strong>{{ node.name }}</strong>
                  <span>{{ node.virtual_ip || '未设置虚拟 IP' }}</span>
                </div>
                <div class="tag-node-card__tags">
                  <el-tag
                    v-for="tag in node.tags"
                    :key="tag"
                    closable
                    type="info"
                    @close="removeTagFromNode(node, tag)"
                  >
                    {{ tag }}
                  </el-tag>
                  <span v-if="!node.tags.length" class="node-card__empty">无标签</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </el-dialog>
    </template>
  </div>
</template>

<style scoped>
.config-overview { display: grid; gap: 20px; }
.view-feedback { padding: 18px 20px; border: 1px solid #d8e1dd; border-radius: 8px; background: #f8fbf9; color: #556a62; box-shadow: var(--app-shadow-sm); }
.view-feedback--silent { min-height: 96px; background: transparent; border-color: transparent; box-shadow: none; }
.view-feedback--error { border-color: #f0d4d4; background: #fff7f7; color: #9a4b4b; }
.config-header-card { padding: 22px; border: 1px solid #d8e1dd; border-radius: 8px; background: linear-gradient(180deg, #ffffff 0%, #fbfdfc 100%); box-shadow: 0 14px 38px rgba(42, 65, 58, 0.07); }
.cfg-top-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.cfg-name-group { display: flex; align-items: center; gap: 10px; }
.cfg-name { color: #1f2d28; font-size: 30px; font-weight: 750; line-height: 1.2; letter-spacing: 0; }
.cfg-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.cfg-desc-row { margin-top: 10px; }
.cfg-desc { color: #62766e; line-height: 1.6; }
.cfg-props-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.cfg-prop-item { display: grid; gap: 8px; padding: 14px; border: 1px solid #dfe9e5; border-radius: 8px; background: #f7fbf9; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75); }
.cfg-prop-label { color: #73877f; font-size: 12px; }
.cfg-prop-value { color: #21302a; font-weight: 700; }
.node-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 18px; padding-top: 18px; border-top: 1px solid #e0e8e4; }
.node-toolbar__actions, .node-toolbar__filters { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.nodes-section { display: grid; gap: 16px; }
.node-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.node-card { display: grid; gap: 14px; padding: 18px; border: 1px solid #d8e1dd; border-radius: 8px; background: #fff; text-align: left; cursor: pointer; box-shadow: 0 10px 26px rgba(42, 65, 58, 0.06); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }
.node-card:hover, .node-strip-card:hover { transform: translateY(-2px); border-color: #9bc8bf; box-shadow: 0 18px 34px rgba(42, 65, 58, 0.11); }
.node-card:focus-visible, .node-strip-card:focus-visible, .tag-card:focus-visible { outline: 3px solid rgba(15, 139, 141, 0.24); outline-offset: 2px; }
.node-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.node-card__head h3 { margin: 0; color: #213029; font-size: 19px; }
.node-card__meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
.node-card__meta dt { color: #73877f; font-size: 12px; }
.node-card__meta dd { margin: 5px 0 0; color: #1f2d28; font-weight: 700; word-break: break-word; }
.node-card__tags, .node-strip-card__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.node-card__empty { color: #70837c; font-size: 13px; }
.node-strip-grid { display: grid; gap: 12px; }
.node-strip-card { display: grid; grid-template-columns: minmax(220px, 1.2fr) minmax(320px, 2fr); gap: 16px; align-items: center; padding: 16px 18px; border: 1px solid #d8e1dd; border-radius: 8px; background: linear-gradient(90deg, #ffffff 0%, #fbfdfc 100%); text-align: left; cursor: pointer; box-shadow: 0 10px 26px rgba(42, 65, 58, 0.055); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }
.node-strip-card__main { display: grid; gap: 10px; }
.node-strip-card__title { display: flex; align-items: center; gap: 10px; }
.node-strip-card__title h3 { margin: 0; color: #213029; font-size: 18px; }
.node-strip-card__facts { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; color: #4d625a; }
.node-strip-card__facts span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-manager { display: grid; gap: 16px; }
.tag-manager__hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 16px; border: 1px solid #e0e8e4; border-radius: 8px; background: #f8fbf9; }
.tag-manager__hero h3 { margin: 0; color: #1f2d28; }
.tag-manager__hero p { margin: 6px 0 0; color: #70837c; }
.tag-create-panel { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
.tag-manager__split { display: grid; grid-template-columns: minmax(220px, 0.8fr) minmax(320px, 1.2fr); gap: 16px; }
.tag-manager__section { display: grid; align-content: start; gap: 12px; min-width: 0; }
.tag-manager__section-head { display: grid; gap: 10px; }
.tag-manager__section-head h4 { margin: 0; color: var(--app-text); }
.tag-manager__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.tag-card { display: grid; gap: 10px; padding: 12px; border: 1px solid #d8e1dd; border-radius: 8px; background: #fff; text-align: left; transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }
.tag-card:hover { transform: translateY(-1px); border-color: #9bc8bf; box-shadow: 0 12px 24px rgba(42, 65, 58, 0.08); }
.tag-card--active { border-color: #0f8b8d; background: #eef8f7; }
.tag-card__body { display: grid; gap: 6px; padding: 0; border: 0; background: transparent; text-align: left; cursor: pointer; }
.tag-card__name { color: #213029; font-weight: 700; }
.tag-card__count, .tag-manager__empty { color: #70837c; font-size: 13px; }
.tag-assign-button { justify-self: start; }
.tag-node-list { display: grid; gap: 10px; max-height: 360px; overflow: auto; padding-right: 4px; }
.tag-node-card { display: grid; gap: 10px; padding: 12px; border: 1px solid #e0e8e4; border-radius: 8px; background: #fff; }
.tag-node-card strong, .tag-node-card span { display: block; }
.tag-node-card strong { color: var(--app-text); }
.tag-node-card span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
.tag-node-card__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.soft-action { border-color: #c9ddd7; background: #f6fbf9; color: #2f5f57; }
.settings-danger-zone { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 18px; padding: 14px; border: 1px solid #f0d4d4; border-radius: 8px; background: #fff8f8; }
.settings-danger-zone__title { color: #7f1d1d; font-weight: 700; }
.settings-danger-zone__desc { margin-top: 4px; color: #8a5c5c; font-size: 13px; }
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
@media (max-width: 1100px) {
  .cfg-props-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .node-toolbar { align-items: stretch; flex-direction: column; }
  .node-strip-card { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .cfg-top-bar, .tag-manager__hero { flex-direction: column; align-items: stretch; }
  .cfg-props-grid, .node-card__meta, .node-strip-card__facts, .form-grid, .tag-create-panel, .tag-manager__split { grid-template-columns: 1fr; }
  .settings-danger-zone, .switch-row { flex-direction: column; align-items: stretch; }
}
</style>
