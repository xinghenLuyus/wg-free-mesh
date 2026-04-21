<script setup lang="ts">
import { ArrowLeft, Key, Plus } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigRead, NodeRead } from '@/types/api'
import { notify } from '@/utils/notify'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

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
const dialogTitle = computed(() => (editingNodeId.value ? t('nodes.editNode') : t('nodes.newNode')))

function nodeTypeLabel(type: NodeRead['node_type']) {
  return type === 'static' ? t('nodeWorkspace.staticNode') : t('nodeWorkspace.dynamicNode')
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
      notify.success(t('nodes.saved'))
    } else {
      await api.createNode(String(route.params.configId), form)
      notify.success(t('nodes.created'))
    }
    dialogVisible.value = false
    await loadNodes()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('nodes.saveFailed'))
  }
}

async function deleteNode(node: NodeRead) {
  try {
    await ElMessageBox.confirm(t('nodes.deleteConfirm', { name: node.name }), t('nodes.deleteTitle'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
    await api.deleteNode(node.id)
    await loadNodes()
    notify.success(t('nodes.deleted'))
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
    notify.error(error instanceof ApiClientError ? error.message : t('nodes.loadFailed'))
  }
})
</script>

<template>
  <section class="content-band">
    <div class="section-head">
      <div>
        <h3>{{ config?.name || t('nodeWorkspace.localConfig') }} - {{ t('nodes.nodeManagement') }}</h3>
        <p class="section-subtitle">{{ t('nodes.subtitle', { count: nodeCount }) }}</p>
      </div>
      <div class="section-actions">
        <el-button :icon="ArrowLeft" @click="router.push(`/configs/${route.params.configId}`)">{{ t('nodes.backOverview') }}</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('nodes.newNode') }}</el-button>
      </div>
    </div>

    <el-table :data="nodes" row-key="id">
      <el-table-column prop="name" :label="t('fields.name')" min-width="150" />
      <el-table-column :label="t('configOverview.type')" width="110">
        <template #default="{ row }">{{ nodeTypeLabel(row.node_type) }}</template>
      </el-table-column>
      <el-table-column prop="virtual_ip" :label="t('nodeWorkspace.virtualIp')" min-width="140" />
      <el-table-column prop="ipv4_address" :label="t('nodeWorkspace.publicIpv4')" min-width="160" />
      <el-table-column prop="ipv6_address" :label="t('nodeWorkspace.publicIpv6')" min-width="160" />
      <el-table-column prop="listen_port" :label="t('nodeWorkspace.listenPort')" width="100" />
      <el-table-column :label="t('configOverview.tags')" min-width="140">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag v-for="tag in row.tags" :key="tag" type="info">{{ tag }}</el-tag>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column :label="t('nodes.actions')" width="320">
        <template #default="{ row }">
          <el-space>
            <el-button size="small" @click="openEdit(row)">{{ t('nodes.edit') }}</el-button>
            <el-button size="small" @click="goTo('mesh', row.id)">Mesh</el-button>
            <el-button size="small" @click="goTo('apply', row.id)">{{ t('nodes.apply') }}</el-button>
            <el-button size="small" type="primary" plain @click="goTo('control', row.id)">{{ t('nodes.control') }}</el-button>
            <el-button size="small" type="danger" plain @click="deleteNode(row)">{{ t('common.delete') }}</el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>
  </section>

  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px">
    <el-form label-position="top">
      <el-form-item :label="t('fields.name')">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item :label="t('configOverview.type')">
        <el-segmented
          v-model="form.node_type"
          :options="[
            { label: t('nodeWorkspace.dynamicNode'), value: 'dynamic' },
            { label: t('nodeWorkspace.staticNode'), value: 'static' },
          ]"
        />
      </el-form-item>
      <el-form-item :label="t('nodeWorkspace.publicIpv4')">
        <el-input v-model="form.ipv4_address" :placeholder="t('nodeWorkspace.ipOrDomain')" />
      </el-form-item>
      <el-form-item :label="t('nodeWorkspace.publicIpv6')">
        <el-input v-model="form.ipv6_address" :placeholder="t('nodeWorkspace.ipOrDomain')" />
      </el-form-item>
      <el-form-item :label="t('nodeWorkspace.listenPort')">
        <el-input-number v-model="form.listen_port" :min="1" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('nodeWorkspace.virtualIp')">
        <el-input v-model="form.virtual_ip">
          <template #append>
            <el-button @click="autofillVirtualIp">{{ t('configOverview.recommend') }}</el-button>
          </template>
        </el-input>
      </el-form-item>
      <el-form-item :label="t('nodeWorkspace.privateKey')">
        <el-input v-model="form.private_key" type="textarea" />
      </el-form-item>
      <el-form-item :label="t('nodeWorkspace.publicKey')">
        <el-input v-model="form.public_key" type="textarea" />
      </el-form-item>
      <el-button plain :icon="Key" @click="autofillKeys">{{ t('nodeWorkspace.generateKeys') }}</el-button>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" @click="submit">{{ t('common.save') }}</el-button>
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
