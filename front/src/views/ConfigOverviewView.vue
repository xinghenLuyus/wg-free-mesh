<script setup lang="ts">
import { CollectionTag, Key, Plus, Setting } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import { useConfigOverviewPrefs } from '@/composables/useConfigOverviewPrefs'
import { useRealtime } from '@/composables/useRealtime'
import type {
  ConfigOverviewNodeCardRead,
  ConfigOverviewRead,
  ConfigOverviewUpdatedPayload,
  NodeRead,
  RealtimeEvent,
  RuntimeSnapshotItem,
  TagRead,
} from '@/types/api'
import { notifyChangeHints } from '@/utils/changeHints'
import { cidrRule, requiredTextRule } from '@/utils/formRules'
import { normalizeTags } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'
import ConfigProtocolForm from '@/components/config/ConfigProtocolForm.vue'
import type { ConfigProtocolModel } from '@/components/config/ConfigProtocolForm.vue'

type ViewMode = 'grid' | 'list'
type SortKey = 'name' | 'virtual_ip' | 'created_at' | 'online' | 'node_type'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const savingConfig = actions.isPending('save-config')
const deletingConfig = actions.isPending('delete-config')
const togglingConfigEnabled = actions.isPending('toggle-config-enabled')
const creatingTag = actions.isPending('create-tag')
const applyingTag = actions.isPending('apply-tag')
const generatingNodeKeys = actions.isPending('generate-node-keys')
const suggestingNodeIp = actions.isPending('suggest-node-ip')
const creatingNode = actions.isPending('create-node')
const overview = shallowRef<ConfigOverviewRead | null>(null)
const fullNodes = shallowRef<NodeRead[]>([])
const tags = shallowRef<TagRead[]>([])
const settingsVisible = shallowRef(false)
const settingsAdvanced = shallowRef(false)
const createVisible = shallowRef(false)
const tagVisible = shallowRef(false)
const configId = computed(() => String(route.params.configId || ''))
const { viewMode, sortKey, tagFilter } = useConfigOverviewPrefs(configId)
const tagSearch = shallowRef('')
const newTagName = shallowRef('')
const selectedTagForAssignment = shallowRef('')
const selectedNodeIds = shallowRef<string[]>([])
const loading = shallowRef(false)
const loadError = shallowRef('')
let loadTicket = 0
let lastRealtimeVersion = 0
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'config.overview.updated') {
    const payload = event.payload as unknown as ConfigOverviewUpdatedPayload
    if (payload.config_id !== String(route.params.configId)) return
    overview.value = payload.overview
    fullNodes.value = payload.overview.nodes
    tags.value = payload.tags
    return
  }
  if (event.type === 'runtime.snapshot.updated' && overview.value) {
    const payload = event.payload as { config_id?: string; items?: RuntimeSnapshotItem[] }
    if (payload.config_id !== String(route.params.configId) || !Array.isArray(payload.items)) return
    const runtimeByNodeId = new Map(payload.items.map((item) => [item.node_id, item]))
    const activeDynamicIds = new Set(overview.value.node_cards.filter((card) => card.node_type === 'dynamic').map((card) => card.id))
    overview.value = {
      ...overview.value,
      stats: {
        ...overview.value.stats,
        online_nodes: payload.items.filter((item) => activeDynamicIds.has(item.node_id) && item.online).length,
      },
      runtime_snapshot: payload.items,
      node_cards: overview.value.node_cards.map((card) => {
        const runtime = runtimeByNodeId.get(card.id)
        if (!runtime) return card
        return {
          ...card,
          online: card.node_type === 'dynamic' ? runtime.online : false,
          peers_total: runtime.peers_total,
        }
      }),
      disabled_node_cards: (overview.value.disabled_node_cards ?? []).map((card) => ({ ...card, online: false, peers_total: 0 })),
    }
  }
})
const settingsFormRef = shallowRef<FormInstance>()
const createFormRef = shallowRef<FormInstance>()

const settingsForm = reactive({
  name: '',
  description: '',
  enabled: true,
  virtual_subnet: '',
  default_listen_port: 51820,
  default_mtu: 1420 as number | null,
  default_dns: '' as string | null,
  auto_sync: true,
  tunnel_protocol: 'wireguard',
  awg_s1: null,
  awg_s2: null,
  awg_s3: null,
  awg_s4: null,
  awg_h1: null,
  awg_h2: null,
  awg_h3: null,
  awg_h4: null,
} satisfies ConfigProtocolModel & {
  name: string
  description: string
  enabled: boolean
  virtual_subnet: string
  default_listen_port: number
  default_mtu: number | null
  default_dns: string | null
  auto_sync: boolean
})
const settingsProtocolForm = computed<ConfigProtocolModel>({
  get: () => settingsForm,
  set: (next) => Object.assign(settingsForm, next),
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
const settingsRules: FormRules<typeof settingsForm> = {
  name: [requiredTextRule('fields.name')],
  virtual_subnet: [cidrRule('configOverview.virtualSubnet')],
}
const createRules: FormRules<typeof createForm> = {
  name: [requiredTextRule('fields.name')],
  virtual_ip: [requiredTextRule('fields.virtualIp')],
}

const nodeCards = computed(() => overview.value?.node_cards ?? [])
const disabledNodeCards = computed(() => overview.value?.disabled_node_cards ?? [])

const tagUsages = computed(() => tags.value)

const allTags = computed(() => tags.value.map((tag) => tag.name))

const visibleTagUsages = computed(() => {
  const keyword = tagSearch.value.trim().toLowerCase()
  if (!keyword) return tagUsages.value
  return tagUsages.value.filter((tag) => tag.name.toLowerCase().includes(keyword))
})

function sortedNodeCards(cards: ConfigOverviewNodeCardRead[]) {
  const filtered = tagFilter.value ? cards.filter((node) => node.tags.includes(tagFilter.value)) : cards
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
  const compareText = (left: string | null | undefined, right: string | null | undefined) => {
    const leftValue = String(left || '').trim()
    const rightValue = String(right || '').trim()
    if (!leftValue && !rightValue) return 0
    if (!leftValue) return 1
    if (!rightValue) return -1
    return collator.compare(leftValue, rightValue)
  }

  return [...filtered].sort((left: ConfigOverviewNodeCardRead, right: ConfigOverviewNodeCardRead) => {
    if (sortKey.value === 'online') {
      const onlineDiff = Number(right.online) - Number(left.online)
      return onlineDiff || compareText(left.name, right.name)
    }
    if (sortKey.value === 'created_at') {
      return right.created_at.localeCompare(left.created_at) || compareText(left.name, right.name)
    }
    if (sortKey.value === 'node_type') {
      const typeDiff = compareText(nodeTypeLabel(left.node_type), nodeTypeLabel(right.node_type))
      return typeDiff || compareText(left.name, right.name)
    }
    if (sortKey.value === 'virtual_ip') {
      const ipDiff = compareText(left.virtual_ip, right.virtual_ip)
      return ipDiff || compareText(left.name, right.name)
    }
    return compareText(left.name, right.name)
  })
}

const visibleNodes = computed(() => sortedNodeCards(nodeCards.value))
const visibleDisabledNodes = computed(() => sortedNodeCards(disabledNodeCards.value))

const topologyInvalid = computed(() => overview.value?.topology.valid === false)

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? t('nodeWorkspace.staticNode') : t('nodeWorkspace.dynamicNode')
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
    loadError.value = error instanceof ApiClientError ? error.message : t('configOverview.loadFailed')
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
    tunnel_protocol: overview.value.config.tunnel_protocol,
    awg_s1: overview.value.config.awg_s1,
    awg_s2: overview.value.config.awg_s2,
    awg_s3: overview.value.config.awg_s3,
    awg_s4: overview.value.config.awg_s4,
    awg_h1: overview.value.config.awg_h1,
    awg_h2: overview.value.config.awg_h2,
    awg_h3: overview.value.config.awg_h3,
    awg_h4: overview.value.config.awg_h4,
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
    auto_sync: overview.value?.config.auto_sync ?? true,
    node_type: 'dynamic',
    public_key: '',
    private_key: '',
    tags_text: '',
  })
}

function openSettings() {
  fillSettingsForm()
  settingsAdvanced.value = false
  settingsVisible.value = true
}

async function openCreate() {
  resetCreateForm()
  createVisible.value = true
  try {
    const suggestion = await api.suggestIp(String(route.params.configId))
    createForm.virtual_ip = suggestion.ip
  } catch {
    // Suggestion failure does not block manual input.
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
    notify.warning(t('configOverview.tagNameRequired'))
    return
  }
  await actions.run('create-tag', async () => {
    try {
      const createdTag = await api.createTag(String(route.params.configId), tag)
      selectedTagForAssignment.value = createdTag.name
      newTagName.value = ''
      await load()
      notify.success(t('configOverview.tagCreated'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('configOverview.tagCreateFailed'))
    }
  })
}

async function applySelectedTagToNodes() {
  const tag = selectedTagForAssignment.value.trim()
  if (!tag) {
    notify.warning(t('configOverview.tagRequired'))
    return
  }
  if (!selectedNodeIds.value.length) {
    notify.warning(t('configOverview.nodesRequired'))
    return
  }

  await actions.run('apply-tag', async () => {
    try {
      await api.applyTagToNodes(String(route.params.configId), tag, selectedNodeIds.value)
      await load()
      selectedNodeIds.value = []
      selectedTagForAssignment.value = tag
      notify.success(t('configOverview.tagApplied'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('configOverview.tagApplyFailed'))
    }
  })
}

async function removeTagFromNode(node: NodeRead, tag: string) {
  try {
    await api.removeTagFromNode(node.id, tag)
    await load()
    notify.success(t('configOverview.tagRemoved'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('configOverview.tagRemoveFailed'))
  }
}

async function deleteTag(tag: string) {
  try {
    await ElMessageBox.confirm(t('configOverview.deleteTagConfirm', { tag }), t('configOverview.deleteTag'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
    await api.deleteTag(String(route.params.configId), tag)
    if (tagFilter.value === tag) clearTagFilter()
    if (selectedTagForAssignment.value === tag) selectedTagForAssignment.value = ''
    await load()
    notify.success(t('configOverview.tagDeleted'))
  } catch (error) {
    if (error instanceof ApiClientError) {
      notify.error(error.message)
    }
  }
}

async function saveSettings() {
  await actions.run('save-config', async () => {
    const valid = settingsAdvanced.value ? true : await settingsFormRef.value?.validate().catch(() => false)
    if (!valid) return
    try {
      const result = await api.updateConfig(String(route.params.configId), { ...settingsForm })
      settingsVisible.value = false
      await load()
      notify.success(t('configOverview.configSaved'))
      notifyChangeHints(result.change_hints)
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('configOverview.configSaveFailed'))
    }
  })
}

async function deleteConfig() {
  if (!overview.value) return
  try {
    await ElMessageBox.confirm(t('configOverview.deleteConfigConfirm', { name: overview.value.config.name }), t('configOverview.deleteConfig'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
  } catch (error) {
    if (error instanceof ApiClientError) {
      notify.error(error.message)
    }
    return
  }
  await actions.run('delete-config', async () => {
    try {
      await api.deleteConfig(String(route.params.configId))
      notify.success(t('configOverview.configDeleted'))
      settingsVisible.value = false
      await router.push('/')
    } catch (error) {
      if (error instanceof ApiClientError) {
        notify.error(error.message)
      }
    }
  })
}

async function toggleEnabled(value: boolean) {
  if (!overview.value) return
  await actions.run('toggle-config-enabled', async () => {
    try {
      await api.updateConfig(String(route.params.configId), {
        ...overview.value!.config,
        enabled: value,
      })
      await load()
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('configOverview.enabledSaveFailed'))
    }
  })
}

async function autofillKeys() {
  await actions.run('generate-node-keys', async () => {
    const keys = await api.generateKeys()
    createForm.private_key = keys.private_key
    createForm.public_key = keys.public_key
  })
}

async function autofillVirtualIp() {
  await actions.run('suggest-node-ip', async () => {
    const suggestion = await api.suggestIp(String(route.params.configId))
    createForm.virtual_ip = suggestion.ip
  })
}

async function createNode() {
  await actions.run('create-node', async () => {
    const valid = await createFormRef.value?.validate().catch(() => false)
    if (!valid) return
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
        enabled: true,
        node_type: createForm.node_type,
        public_key: createForm.public_key,
        private_key: createForm.private_key,
        tags,
      })
      createVisible.value = false
      await load()
      notify.success(t('configOverview.endpointCreated'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('configOverview.endpointCreateFailed'))
    }
  })
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
      notify.error(loadError.value || t('configOverview.loadFailed'))
    }
  },
)

watch(
  [allTags, tagFilter],
  ([nextTags, nextTagFilter]) => {
    if (!overview.value) return
    if (nextTagFilter && !nextTags.includes(nextTagFilter)) {
      tagFilter.value = ''
    }
  },
)

onMounted(async () => {
  try {
    await load()
    realtime.connect()
    lastRealtimeVersion = realtime.connectionVersion.value
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('configOverview.loadFailed'))
  }
})

watch(
  () => realtime.connectionVersion.value,
  async (nextVersion) => {
    if (nextVersion <= 0) return
    if (lastRealtimeVersion === 0) {
      lastRealtimeVersion = nextVersion
      return
    }
    lastRealtimeVersion = nextVersion
    try {
      await load()
    } catch {
      // Keep reconnect reconciliation silent.
    }
  },
)
</script>

<template>
  <div class="config-overview">
    <div v-if="loading && !overview" class="view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !overview" class="view-feedback view-feedback--error">{{ loadError }}</div>
    <template v-else-if="overview">
    <div class="config-header-card" :class="{ 'config-header-card--danger': topologyInvalid }">
      <div class="cfg-top-bar">
        <div class="cfg-name-group">
          <span class="cfg-name">{{ overview.config.name }}</span>
          <el-tag v-if="topologyInvalid" type="danger" effect="dark">{{ t('configOverview.topologyFailed') }}</el-tag>
        </div>
        <div class="cfg-actions">
          <el-switch
            :model-value="overview.config.enabled"
            :loading="togglingConfigEnabled"
            :disabled="togglingConfigEnabled"
            inline-prompt
            :active-text="t('common.enabled')"
            :inactive-text="t('common.disabled')"
            @change="(value: boolean | string | number) => toggleEnabled(Boolean(value))"
          />
          <el-button size="small" type="primary" plain :icon="Setting" @click="openSettings">{{ t('configOverview.settings') }}</el-button>
        </div>
      </div>

      <div class="cfg-desc-row">
        <span class="cfg-desc">{{ overview.config.description || t('configOverview.noDescription') }}</span>
      </div>

      <div class="cfg-props-grid">
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">{{ t('configOverview.virtualSubnet') }}</span>
          <span class="cfg-prop-value">{{ overview.config.virtual_subnet }}</span>
        </div>
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">{{ t('configOverview.defaultListenPort') }}</span>
          <span class="cfg-prop-value">{{ overview.config.default_listen_port }}</span>
        </div>
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">{{ t('configOverview.defaultMtu') }}</span>
          <span class="cfg-prop-value">{{ overview.config.default_mtu || t('nodeWorkspace.unset') }}</span>
        </div>
        <div class="cfg-prop-item">
          <span class="cfg-prop-label">{{ t('configOverview.defaultDns') }}</span>
          <span class="cfg-prop-value">{{ overview.config.default_dns || t('nodeWorkspace.unset') }}</span>
        </div>
      </div>

      <div class="node-toolbar">
        <div class="node-toolbar__actions">
          <el-button class="soft-action" :icon="CollectionTag" @click="openTagManager">{{ t('configOverview.tagManager') }}</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('configOverview.createEndpoint') }}</el-button>
        </div>
        <div class="node-toolbar__filters">
          <el-select v-model="sortKey" style="width: 140px">
            <el-option :label="t('configOverview.sortName')" value="name" />
            <el-option :label="t('configOverview.sortVirtualIp')" value="virtual_ip" />
            <el-option :label="t('configOverview.sortCreatedAt')" value="created_at" />
            <el-option :label="t('configOverview.sortOnline')" value="online" />
            <el-option :label="t('configOverview.sortNodeType')" value="node_type" />
          </el-select>
          <el-select v-model="tagFilter" clearable :placeholder="t('configOverview.filterByTag')" style="width: 160px">
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
          <el-segmented v-model="viewMode" :options="[
            { label: t('configOverview.grid'), value: 'grid' },
            { label: t('configOverview.list'), value: 'list' },
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
            <div class="node-card__status-tags">
              <el-tag v-if="node.mesh_error" type="danger">{{ t('configOverview.meshError') }}</el-tag>
              <el-tag v-if="node.node_type === 'dynamic'" :type="node.online ? 'success' : 'info'">{{ node.online ? t('nodeWorkspace.online') : t('nodeWorkspace.offline') }}</el-tag>
            </div>
          </div>
          <dl class="node-card__meta">
            <div>
              <dt>{{ t('configOverview.type') }}</dt>
              <dd>{{ nodeTypeLabel(node.node_type) }}</dd>
            </div>
            <div>
              <dt>{{ t('nodeWorkspace.virtualIp') }}</dt>
              <dd>{{ node.virtual_ip || t('nodeWorkspace.unset') }}</dd>
            </div>
            <div>
              <dt>{{ t('nodeWorkspace.publicIpv4') }}</dt>
              <dd>{{ node.ipv4_address || t('nodeWorkspace.unset') }}</dd>
            </div>
            <div>
              <dt>{{ t('nodeWorkspace.publicIpv6') }}</dt>
              <dd>{{ node.ipv6_address || t('nodeWorkspace.unset') }}</dd>
            </div>
          </dl>
          <div class="node-card__tags">
            <el-tag v-for="tag in node.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
            <span v-if="!node.tags.length" class="node-card__empty">{{ t('configOverview.noTags') }}</span>
          </div>
        </button>
      </div>

      <div v-if="viewMode === 'grid' && visibleDisabledNodes.length" class="disabled-node-section">
        <div class="disabled-node-section__head">
          <span>{{ t('configOverview.disabledEndpoints') }}</span>
          <el-tag type="info" size="small">{{ visibleDisabledNodes.length }}</el-tag>
        </div>
        <div class="node-grid">
          <button
            v-for="node in visibleDisabledNodes"
            :key="node.id"
            class="node-card node-card--disabled"
            @click="openNode(node.id)"
          >
            <div class="node-card__head">
              <h3>{{ node.name }}</h3>
              <div class="node-card__status-tags">
                <el-tag type="info">{{ t('nodeWorkspace.disabledEndpoint') }}</el-tag>
                <el-tag v-if="node.mesh_error" type="danger">{{ t('configOverview.meshError') }}</el-tag>
              </div>
            </div>
            <dl class="node-card__meta">
              <div>
                <dt>{{ t('configOverview.type') }}</dt>
                <dd>{{ nodeTypeLabel(node.node_type) }}</dd>
              </div>
              <div>
                <dt>{{ t('nodeWorkspace.virtualIp') }}</dt>
                <dd>{{ node.virtual_ip || t('nodeWorkspace.unset') }}</dd>
              </div>
              <div>
                <dt>{{ t('nodeWorkspace.publicIpv4') }}</dt>
                <dd>{{ node.ipv4_address || t('nodeWorkspace.unset') }}</dd>
              </div>
              <div>
                <dt>{{ t('nodeWorkspace.publicIpv6') }}</dt>
                <dd>{{ node.ipv6_address || t('nodeWorkspace.unset') }}</dd>
              </div>
            </dl>
            <div class="node-card__tags">
              <el-tag v-for="tag in node.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
              <span v-if="!node.tags.length" class="node-card__empty">{{ t('configOverview.noTags') }}</span>
            </div>
          </button>
        </div>
      </div>

      <div v-if="viewMode === 'list'" class="node-strip-grid">
        <button
          v-for="node in visibleNodes"
          :key="node.id"
          class="node-strip-card"
          @click="openNode(node.id)"
        >
          <div class="node-strip-card__main">
            <div class="node-strip-card__title">
              <div class="node-strip-card__title-copy">
                <h3>{{ node.name }}</h3>
                <p>{{ nodeTypeLabel(node.node_type) }}</p>
              </div>
              <div class="node-strip-card__status-tags">
                <el-tag v-if="node.mesh_error" type="danger" size="small">{{ t('configOverview.meshError') }}</el-tag>
                <el-tag v-if="node.node_type === 'dynamic'" :type="node.online ? 'success' : 'info'" size="small">{{ node.online ? t('nodeWorkspace.online') : t('nodeWorkspace.offline') }}</el-tag>
              </div>
            </div>
            <div class="node-strip-card__tags">
              <el-tag v-for="tag in node.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
              <span v-if="!node.tags.length" class="node-card__empty">{{ t('configOverview.noTags') }}</span>
            </div>
          </div>
          <div class="node-strip-card__facts">
            <div class="node-strip-card__fact">
              <span class="node-strip-card__fact-label">{{ t('nodeWorkspace.virtualIp') }}</span>
              <span class="node-strip-card__fact-value">{{ node.virtual_ip || t('configOverview.unsetVirtualIp') }}</span>
            </div>
            <div class="node-strip-card__fact">
              <span class="node-strip-card__fact-label">{{ t('nodeWorkspace.publicIpv4') }}</span>
              <span class="node-strip-card__fact-value">{{ node.ipv4_address || t('nodeWorkspace.unset') }}</span>
            </div>
            <div class="node-strip-card__fact">
              <span class="node-strip-card__fact-label">{{ t('nodeWorkspace.publicIpv6') }}</span>
              <span class="node-strip-card__fact-value">{{ node.ipv6_address || t('nodeWorkspace.unset') }}</span>
            </div>
          </div>
        </button>
      </div>
      <div v-if="viewMode === 'list' && visibleDisabledNodes.length" class="disabled-node-section">
        <div class="disabled-node-section__head">
          <span>{{ t('configOverview.disabledEndpoints') }}</span>
          <el-tag type="info" size="small">{{ visibleDisabledNodes.length }}</el-tag>
        </div>
        <div class="node-strip-grid">
          <button
            v-for="node in visibleDisabledNodes"
            :key="node.id"
            class="node-strip-card node-strip-card--disabled"
            @click="openNode(node.id)"
          >
            <div class="node-strip-card__main">
              <div class="node-strip-card__title">
                <div class="node-strip-card__title-copy">
                  <h3>{{ node.name }}</h3>
                  <p>{{ nodeTypeLabel(node.node_type) }}</p>
                </div>
                <div class="node-strip-card__status-tags">
                  <el-tag type="info" size="small">{{ t('nodeWorkspace.disabledEndpoint') }}</el-tag>
                  <el-tag v-if="node.mesh_error" type="danger" size="small">{{ t('configOverview.meshError') }}</el-tag>
                </div>
              </div>
              <div class="node-strip-card__tags">
                <el-tag v-for="tag in node.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
                <span v-if="!node.tags.length" class="node-card__empty">{{ t('configOverview.noTags') }}</span>
              </div>
            </div>
            <div class="node-strip-card__facts">
              <div class="node-strip-card__fact">
                <span class="node-strip-card__fact-label">{{ t('nodeWorkspace.virtualIp') }}</span>
                <span class="node-strip-card__fact-value">{{ node.virtual_ip || t('configOverview.unsetVirtualIp') }}</span>
              </div>
              <div class="node-strip-card__fact">
                <span class="node-strip-card__fact-label">{{ t('nodeWorkspace.publicIpv4') }}</span>
                <span class="node-strip-card__fact-value">{{ node.ipv4_address || t('nodeWorkspace.unset') }}</span>
              </div>
              <div class="node-strip-card__fact">
                <span class="node-strip-card__fact-label">{{ t('nodeWorkspace.publicIpv6') }}</span>
                <span class="node-strip-card__fact-value">{{ node.ipv6_address || t('nodeWorkspace.unset') }}</span>
              </div>
            </div>
          </button>
        </div>
      </div>
    </section>

    <el-dialog v-model="settingsVisible" width="560px">
      <template #header="{ titleId, titleClass }">
        <div class="settings-dialog-header">
          <nav class="settings-dialog-tabs" :aria-label="t('configOverview.configSettings')">
            <button
              :id="titleId"
              type="button"
              :class="['settings-dialog-tab', 'settings-dialog-tab--title', titleClass, { 'settings-dialog-tab--active': !settingsAdvanced }]"
              :aria-current="!settingsAdvanced ? 'page' : undefined"
              @click="settingsAdvanced = false"
            >
              {{ t('configOverview.configSettings') }}
            </button>
            <button
              type="button"
              :class="['settings-dialog-tab', 'settings-dialog-tab--title', { 'settings-dialog-tab--active': settingsAdvanced }]"
              :aria-current="settingsAdvanced ? 'page' : undefined"
              @click="settingsAdvanced = true"
            >
              {{ t('protocol.advancedSettings') }}
            </button>
          </nav>
        </div>
      </template>
      <template v-if="!settingsAdvanced">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Setting /></el-icon></span>
        <div>
          <h3>{{ t('configOverview.configBasics') }}</h3>
          <p>{{ t('configOverview.configBasicsDescription') }}</p>
        </div>
      </div>
      <el-form ref="settingsFormRef" :model="settingsForm" :rules="settingsRules" class="dialog-form" label-position="top">
        <el-form-item :label="t('fields.name')" prop="name" required><el-input v-model="settingsForm.name" /></el-form-item>
        <el-form-item :label="t('home.descriptionField')"><el-input v-model="settingsForm.description" type="textarea" :rows="3" /></el-form-item>
        <div class="form-grid">
          <el-form-item :label="t('configOverview.virtualSubnet')" prop="virtual_subnet" required><el-input v-model="settingsForm.virtual_subnet" /></el-form-item>
          <el-form-item :label="t('configOverview.defaultListenPort')">
            <el-input-number v-model="settingsForm.default_listen_port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('configOverview.defaultMtu')">
            <el-input-number v-model="settingsForm.default_mtu" :min="576" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('configOverview.defaultDns')"><el-input v-model="settingsForm.default_dns" /></el-form-item>
        </div>
        <div class="switch-row">
          <div>
            <strong>{{ t('configOverview.defaultNodeAutoSync') }}</strong>
            <span>{{ t('configOverview.defaultNodeAutoSyncDescription') }}</span>
          </div>
          <el-switch v-model="settingsForm.auto_sync" />
        </div>
      </el-form>
      </template>
      <ConfigProtocolForm v-else v-model="settingsProtocolForm" />
      <div class="settings-danger-zone">
        <div>
          <div class="settings-danger-zone__title">{{ t('configOverview.deleteConfig') }}</div>
          <div class="settings-danger-zone__desc">{{ t('configOverview.deleteConfigDescription') }}</div>
        </div>
        <el-button type="danger" plain :loading="deletingConfig" @click="deleteConfig">{{ t('configOverview.deleteConfig') }}</el-button>
      </div>
      <template #footer>
        <el-button @click="settingsVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="savingConfig" @click="saveSettings">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" :title="t('configOverview.createEndpoint')" width="560px">
      <div class="dialog-intro">
        <span class="dialog-intro__icon"><el-icon><Plus /></el-icon></span>
        <div>
          <h3>{{ t('configOverview.endpointIntroTitle') }}</h3>
          <p>{{ t('configOverview.endpointIntroDescription') }}</p>
        </div>
      </div>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" class="dialog-form" label-position="top">
        <el-form-item :label="t('fields.name')" prop="name" required><el-input v-model="createForm.name" :placeholder="t('configOverview.endpointNamePlaceholder')" /></el-form-item>
        <el-form-item :label="t('configOverview.type')">
          <el-segmented
            v-model="createForm.node_type"
            :options="[
              { label: t('nodeWorkspace.dynamicNode'), value: 'dynamic' },
              { label: t('nodeWorkspace.staticNode'), value: 'static' },
            ]"
          />
        </el-form-item>
        <div class="form-grid">
          <el-form-item :label="t('nodeWorkspace.publicIpv4')"><el-input v-model="createForm.ipv4_address" :placeholder="t('nodeWorkspace.ipOrDomain')" /></el-form-item>
          <el-form-item :label="t('nodeWorkspace.publicIpv6')"><el-input v-model="createForm.ipv6_address" :placeholder="t('nodeWorkspace.ipOrDomain')" /></el-form-item>
          <el-form-item :label="t('nodeWorkspace.virtualIp')" prop="virtual_ip" required>
            <el-input v-model="createForm.virtual_ip">
              <template #append><el-button :loading="suggestingNodeIp" @click="autofillVirtualIp">{{ t('configOverview.recommend') }}</el-button></template>
            </el-input>
          </el-form-item>
        </div>
        <el-form-item :label="t('configOverview.tags')">
          <el-input v-model="createForm.tags_text" :placeholder="t('configOverview.tagsPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('nodeWorkspace.privateKey')"><el-input v-model="createForm.private_key" type="textarea" /></el-form-item>
        <el-form-item :label="t('nodeWorkspace.publicKey')"><el-input v-model="createForm.public_key" type="textarea" /></el-form-item>
        <el-button plain :icon="Key" :loading="generatingNodeKeys" @click="autofillKeys">{{ t('nodeWorkspace.generateKeys') }}</el-button>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creatingNode" @click="createNode">{{ t('home.create') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tagVisible" :title="t('configOverview.tagManager')" width="760px">
      <div class="tag-manager">
        <div class="tag-manager__hero">
          <div>
            <h3>{{ t('configOverview.tagTitle') }}</h3>
            <p>{{ t('configOverview.tagDescription') }}</p>
          </div>
          <el-button v-if="tagFilter" @click="clearTagFilter">{{ t('configOverview.clearFilter') }}</el-button>
        </div>

        <div class="tag-create-panel">
          <el-input v-model="newTagName" :placeholder="t('configOverview.newTagName')" clearable @keyup.enter="createTag" />
          <el-button type="primary" :icon="Plus" :loading="creatingTag" @click="createTag">{{ t('configOverview.createTag') }}</el-button>
        </div>

        <div class="tag-manager__split">
          <section class="tag-manager__section">
            <div class="tag-manager__section-head">
              <h4>{{ t('configOverview.tagList') }}</h4>
              <el-input v-model="tagSearch" :placeholder="t('configOverview.searchTag')" clearable />
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
                  <span class="tag-card__count">{{ t('configOverview.tagEndpointCount', { count: tag.count }) }}</span>
                </button>
                <el-button size="small" type="danger" plain @click="deleteTag(tag.name)">{{ t('common.delete') }}</el-button>
              </div>
              <div v-if="!visibleTagUsages.length" class="tag-manager__empty">{{ t('configOverview.noMatchedTags') }}</div>
            </div>
          </section>

          <section class="tag-manager__section">
            <div class="tag-manager__section-head">
              <h4>{{ t('configOverview.endpointTags') }}</h4>
              <el-select v-model="selectedTagForAssignment" :placeholder="t('configOverview.selectTag')" style="width: 100%">
                <el-option v-for="tag in assignableTagOptions" :key="tag" :label="tag" :value="tag" />
              </el-select>
            </div>

            <el-select
              v-model="selectedNodeIds"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              :placeholder="t('configOverview.selectNodes')"
              style="width: 100%"
            >
              <el-option v-for="node in fullNodes" :key="node.id" :label="node.name" :value="node.id" />
            </el-select>
            <el-button type="primary" class="tag-assign-button" :loading="applyingTag" @click="applySelectedTagToNodes">{{ t('configOverview.applyToNodes') }}</el-button>

            <div class="tag-node-list">
              <div v-for="node in fullNodes" :key="node.id" class="tag-node-card">
                <div>
                  <strong>{{ node.name }}</strong>
                  <span>{{ node.virtual_ip || t('configOverview.unsetVirtualIp') }}</span>
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
                  <span v-if="!node.tags.length" class="node-card__empty">{{ t('configOverview.noTags') }}</span>
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
.view-feedback { padding: 18px 20px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); color: var(--app-muted); box-shadow: var(--app-shadow-sm); }
.view-feedback--silent { min-height: 96px; background: transparent; border-color: transparent; box-shadow: none; }
.view-feedback--error { border-color: var(--app-danger-border); background: color-mix(in srgb, var(--app-danger-border) 12%, var(--app-surface-elevated)); color: var(--app-danger-text); }
.config-header-card { padding: 22px; border: 1px solid var(--app-border); border-radius: 8px; background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%); box-shadow: var(--app-shadow-md); }
.config-header-card--danger { border-color: var(--app-danger-border); box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-danger-border) 26%, transparent), var(--app-shadow-md); }
.cfg-top-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.cfg-name-group { display: flex; align-items: center; gap: 10px; }
.cfg-name { color: var(--app-text-strong); font-size: 30px; font-weight: 750; line-height: 1.2; letter-spacing: 0; }
.cfg-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.cfg-desc-row { margin-top: 10px; }
.cfg-desc { color: var(--app-muted); line-height: 1.6; }
.cfg-props-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.cfg-prop-item { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); box-shadow: inset 0 1px 0 color-mix(in srgb, white 14%, transparent); }
.cfg-prop-label { color: var(--app-faint); font-size: 12px; }
.cfg-prop-value { color: var(--app-text-strong); font-weight: 700; }
.node-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--app-border-soft); }
.node-toolbar__actions, .node-toolbar__filters { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.nodes-section { display: grid; gap: 16px; }
.node-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.node-card { display: grid; gap: 14px; padding: 18px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); text-align: left; cursor: pointer; box-shadow: var(--app-shadow-sm); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }
.node-card:hover, .node-strip-card:hover { transform: translateY(-2px); border-color: var(--app-border-accent); box-shadow: var(--app-shadow-md); }
.node-card--disabled,
.node-strip-card--disabled { border-color: var(--app-border-soft); background: color-mix(in srgb, var(--app-surface-sunken) 88%, var(--app-surface)); filter: grayscale(0.22); }
.node-card--disabled h3,
.node-strip-card--disabled h3,
.node-card--disabled dd,
.node-strip-card--disabled .node-strip-card__fact-value { color: var(--app-muted); }
.node-card:focus-visible, .node-strip-card:focus-visible, .tag-card:focus-visible { outline: 0; box-shadow: var(--app-focus), var(--app-shadow-md); }
.node-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.node-card__status-tags, .node-strip-card__status-tags { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.node-card__head h3 { margin: 0; color: var(--app-text-strong); font-size: 19px; }
.node-card__meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
.node-card__meta dt { color: var(--app-faint); font-size: 12px; }
.node-card__meta dd { margin: 5px 0 0; color: var(--app-text-strong); font-weight: 700; word-break: break-word; }
.node-card__tags, .node-strip-card__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.node-card__empty { color: var(--app-faint); font-size: 13px; }
.node-strip-grid { display: grid; gap: 12px; }
.node-strip-card { display: grid; grid-template-columns: minmax(250px, 1.05fr) minmax(420px, 1.45fr); gap: 18px; align-items: stretch; padding: 16px 18px; border: 1px solid var(--app-border); border-radius: 8px; background: linear-gradient(90deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%); text-align: left; cursor: pointer; box-shadow: var(--app-shadow-sm); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }
.node-strip-card__main { display: grid; gap: 12px; min-width: 0; }
.node-strip-card__title { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.node-strip-card__title-copy { display: grid; gap: 4px; min-width: 0; }
.node-strip-card__title h3 { margin: 0; color: var(--app-text-strong); font-size: 18px; }
.node-strip-card__title-copy p { margin: 0; color: var(--app-faint); font-size: 13px; font-weight: 600; }
.node-strip-card__facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.node-strip-card__fact { display: grid; gap: 6px; min-width: 0; padding: 12px 13px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: color-mix(in srgb, var(--app-surface-sunken) 88%, transparent); box-shadow: inset 0 1px 0 color-mix(in srgb, white 10%, transparent); }
.node-strip-card__fact-label { color: var(--app-faint); font-size: 11px; font-weight: 700; letter-spacing: 0; }
.node-strip-card__fact-value { color: var(--app-text-strong); font-size: 14px; font-weight: 700; line-height: 1.35; word-break: break-word; }
.disabled-node-section { display: grid; gap: 12px; margin-top: 12px; padding-top: 16px; border-top: 1px dashed var(--app-border-strong); }
.disabled-node-section__head { display: flex; align-items: center; gap: 8px; color: var(--app-muted); font-weight: 750; }
.tag-manager { display: grid; gap: 16px; }
.tag-manager__hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 16px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); }
.tag-manager__hero h3 { margin: 0; color: var(--app-text-strong); }
.tag-manager__hero p { margin: 6px 0 0; color: var(--app-faint); }
.tag-create-panel { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
.tag-manager__split { display: grid; grid-template-columns: minmax(220px, 0.8fr) minmax(320px, 1.2fr); gap: 16px; }
.tag-manager__section { display: grid; align-content: start; gap: 12px; min-width: 0; }
.tag-manager__section-head { display: grid; gap: 10px; }
.tag-manager__section-head h4 { margin: 0; color: var(--app-text); }
.tag-manager__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.tag-card { display: grid; gap: 10px; padding: 12px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); text-align: left; transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease; }
.tag-card:hover { transform: translateY(-1px); border-color: var(--app-border-accent); box-shadow: var(--app-shadow-sm); }
.tag-card--active { border-color: var(--app-primary); background: var(--app-surface-selected); }
.tag-card__body { display: grid; gap: 6px; padding: 0; border: 0; background: transparent; text-align: left; cursor: pointer; }
.tag-card__name { color: var(--app-text-strong); font-weight: 700; }
.tag-card__count, .tag-manager__empty { color: var(--app-faint); font-size: 13px; }
.tag-assign-button { justify-self: start; }
.tag-node-list { display: grid; gap: 10px; max-height: 360px; overflow: auto; padding-right: 4px; }
.tag-node-card { display: grid; gap: 10px; padding: 12px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-elevated); }
.tag-node-card strong, .tag-node-card span { display: block; }
.tag-node-card strong { color: var(--app-text); }
.tag-node-card span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
.tag-node-card__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.soft-action { border-color: var(--app-border-accent); background: var(--app-surface-sunken); color: var(--app-primary-strong); }
.settings-danger-zone { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 18px; padding: 14px; border: 1px solid var(--app-danger-border); border-radius: 8px; background: color-mix(in srgb, var(--app-danger-border) 12%, var(--app-surface-elevated)); }
.settings-danger-zone__title { color: var(--app-danger-text); font-weight: 700; }
.settings-danger-zone__desc { margin-top: 4px; color: var(--app-warning-text); font-size: 13px; }
.settings-dialog-header { display: flex; align-items: center; padding-right: 42px; }
.settings-dialog-tabs { display: inline-flex; align-items: center; gap: 18px; }
.settings-dialog-tab { appearance: none; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--app-muted); cursor: pointer; font: inherit; font-weight: 700; line-height: 1.3; padding: 4px 0 6px; }
.settings-dialog-tab--title { font-size: 22px; font-weight: 750; }
.settings-dialog-tab:hover { color: var(--app-primary-strong); }
.settings-dialog-tab--active { border-bottom-color: var(--app-primary); color: var(--app-text-strong); }
.dialog-intro { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 18px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); }
.dialog-intro__icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 42px; height: 42px; border: 1px solid var(--app-border-accent); border-radius: 8px; background: var(--app-primary-soft); color: var(--app-primary); }
.dialog-intro h3 { margin: 0; color: var(--app-text); }
.dialog-intro p { margin: 5px 0 0; color: var(--app-muted); line-height: 1.5; }
.dialog-form { display: grid; gap: 2px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-interactive); }
.switch-row strong, .switch-row span { display: block; }
.switch-row strong { color: var(--app-text); }
.switch-row span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
@media (max-width: 1100px) {
  .cfg-props-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .node-toolbar { align-items: stretch; flex-direction: column; }
  .node-strip-card { grid-template-columns: 1fr; }
  .node-strip-card__facts { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .cfg-top-bar, .tag-manager__hero, .node-strip-card__title { flex-direction: column; align-items: stretch; }
  .cfg-props-grid, .node-card__meta, .form-grid, .tag-create-panel, .tag-manager__split { grid-template-columns: 1fr; }
  .settings-danger-zone, .switch-row { flex-direction: column; align-items: stretch; }
}
</style>
