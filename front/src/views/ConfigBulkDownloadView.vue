<script setup lang="ts">
import { ArrowLeft, Box, Download, Files } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ConfigBulkOptionsRead, ConfigBulkPackageRead } from '@/types/api'
import { notify } from '@/utils/notify'

const { t } = useI18n()
const router = useRouter()

const options = shallowRef<ConfigBulkOptionsRead>({ configs: [], nodes: [] })
const selectedConfigId = shallowRef('')
const selectedNodeIds = shallowRef<string[]>([])
const packageInfo = shallowRef<ConfigBulkPackageRead | null>(null)
const loading = shallowRef(false)
const packaging = shallowRef(false)
const loadError = shallowRef('')
let loadingTicket = 0

const selectedConfig = computed(() => options.value.configs.find((item) => item.id === selectedConfigId.value))
const downloadableNodes = computed(() => options.value.nodes.filter((node) => node.can_download))
const allDownloadableSelected = computed(() =>
  downloadableNodes.value.length > 0 && downloadableNodes.value.every((node) => selectedNodeIds.value.includes(node.id)),
)
const selectedCountText = computed(() => t('tools.configBulkDownload.selectedCount', { count: selectedNodeIds.value.length }))

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function loadOptions(configId = selectedConfigId.value) {
  const ticket = ++loadingTicket
  loading.value = true
  loadError.value = ''
  try {
    const nextOptions = await api.configBulkOptions(configId || undefined)
    if (ticket !== loadingTicket) return
    options.value = nextOptions
    if (!selectedConfigId.value && nextOptions.configs.length) {
      selectedConfigId.value = nextOptions.configs[0].id
      return
    }
    selectedNodeIds.value = nextOptions.nodes.filter((node) => node.can_download).map((node) => node.id)
  } catch (error) {
    if (ticket !== loadingTicket) return
    loadError.value = error instanceof ApiClientError ? error.message : t('tools.configBulkDownload.loadFailed')
    notify.error(loadError.value)
  } finally {
    if (ticket === loadingTicket) loading.value = false
  }
}

function toggleSelectAll(value: boolean) {
  selectedNodeIds.value = value ? downloadableNodes.value.map((node) => node.id) : []
}

async function createAndDownloadPackage() {
  if (!selectedConfigId.value) return
  packaging.value = true
  try {
    const nextPackage = await api.createConfigBulkPackage({
      config_id: selectedConfigId.value,
      node_ids: selectedNodeIds.value,
    })
    packageInfo.value = nextPackage
    const blob = await api.downloadConfigBulkPackage(nextPackage.package_id)
    saveBlob(blob, nextPackage.filename)
    notify.success(t('tools.configBulkDownload.packageReady'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('tools.configBulkDownload.packageFailed'))
  } finally {
    packaging.value = false
  }
}

function backToDownloadTools() {
  void router.push('/tools/download')
}

watch(
  selectedConfigId,
  async (configId) => {
    if (!configId) return
    packageInfo.value = null
    await loadOptions(configId)
  },
)

onMounted(() => {
  void loadOptions()
})
</script>

<template>
  <section class="tool-page">
    <div class="tool-hero">
      <div class="tool-hero__copy">
        <el-button class="tool-hero__back" :icon="ArrowLeft" plain @click="backToDownloadTools">{{ t('tools.download.back') }}</el-button>
        <div>
          <p class="tool-hero__eyebrow">{{ t('layout.toolList') }}</p>
          <h1>{{ t('tools.configBulkDownload.title') }}</h1>
          <p>{{ t('tools.configBulkDownload.description') }}</p>
        </div>
      </div>
      <el-icon><Files /></el-icon>
    </div>

    <div v-if="loading && !options.configs.length" class="content-band view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !options.configs.length" class="content-band view-feedback view-feedback--error">{{ loadError }}</div>
    <div v-else class="bulk-layout">
      <article class="bulk-panel bulk-panel--controls">
        <div class="bulk-panel__head">
          <el-icon><Box /></el-icon>
          <div>
            <h2>{{ t('tools.configBulkDownload.config') }}</h2>
            <p>{{ selectedConfig?.name || t('tools.configBulkDownload.noConfigs') }}</p>
          </div>
        </div>

        <el-form label-position="top">
          <el-form-item :label="t('tools.configBulkDownload.config')">
            <el-select v-model="selectedConfigId" :placeholder="t('tools.configBulkDownload.noConfigs')" :disabled="!options.configs.length">
              <el-option v-for="config in options.configs" :key="config.id" :label="config.name" :value="config.id" />
            </el-select>
          </el-form-item>
        </el-form>

        <label class="bulk-select-all">
          <el-checkbox :model-value="allDownloadableSelected" :disabled="!downloadableNodes.length" @change="toggleSelectAll(Boolean($event))" />
          <span>{{ t('tools.configBulkDownload.selectAll') }}</span>
        </label>

        <el-button
          type="primary"
          :icon="Download"
          :loading="packaging"
          :disabled="!selectedConfigId || !selectedNodeIds.length"
          @click="createAndDownloadPackage"
        >
          {{ t('tools.configBulkDownload.download') }}
        </el-button>

        <div class="bulk-meta">{{ selectedCountText }}</div>
      </article>

      <article class="bulk-panel">
        <div class="bulk-panel__head">
          <el-icon><Files /></el-icon>
          <div>
            <h2>{{ t('tools.configBulkDownload.endpoints') }}</h2>
            <p>{{ downloadableNodes.length ? selectedCountText : t('tools.configBulkDownload.noNodes') }}</p>
          </div>
        </div>

        <el-checkbox-group v-model="selectedNodeIds" class="endpoint-list">
          <label v-for="node in options.nodes" :key="node.id" class="endpoint-row" :class="{ 'endpoint-row--disabled': !node.can_download }">
            <el-checkbox :value="node.id" :disabled="!node.can_download" />
            <span class="endpoint-row__main">
              <strong>{{ node.name }}</strong>
              <span>{{ node.virtual_ip || t('common.notAvailable') }} · {{ node.node_type }}</span>
            </span>
            <span class="endpoint-row__meta">
              <span v-if="node.can_download">{{ t('tools.configBulkDownload.stagedVersion') }} {{ node.staged_version }}</span>
              <span v-else>{{ t('tools.configBulkDownload.notReady') }}</span>
              <small>{{ t('tools.configBulkDownload.syncStatus') }}: {{ node.sync_status }}</small>
            </span>
          </label>
        </el-checkbox-group>

        <div v-if="!options.nodes.length" class="view-feedback">{{ t('tools.configBulkDownload.noNodes') }}</div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.tool-page { display: grid; gap: 18px; }
.tool-hero {
  display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 172px; padding: 32px;
  border: 1px solid var(--app-border); border-radius: 18px; background: linear-gradient(135deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}
.tool-hero__copy { display: grid; gap: 18px; min-width: 0; }
.tool-hero__back { justify-self: start; }
.tool-hero__eyebrow { margin: 0 0 10px; color: var(--app-primary-strong); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.tool-hero h1 { margin: 0; color: var(--app-text-strong); font-size: 34px; letter-spacing: 0; }
.tool-hero p { max-width: 620px; margin: 10px 0 0; color: var(--app-muted); }
.tool-hero > .el-icon { flex: 0 0 auto; width: 86px; height: 86px; border-radius: 18px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 42px; }
.bulk-layout { display: grid; grid-template-columns: minmax(280px, .7fr) minmax(0, 1.3fr); gap: 18px; align-items: start; }
.bulk-panel { display: grid; gap: 18px; padding: 24px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.bulk-panel--controls { position: sticky; top: 24px; }
.bulk-panel__head { display: flex; gap: 14px; align-items: flex-start; }
.bulk-panel__head > .el-icon { flex: 0 0 auto; width: 42px; height: 42px; border-radius: 10px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 22px; }
.bulk-panel__head h2 { margin: 0; color: var(--app-text-strong); font-size: 18px; letter-spacing: 0; }
.bulk-panel__head p { margin: 6px 0 0; color: var(--app-muted); font-size: 13px; }
.bulk-panel :deep(.el-select) { width: 100%; }
.bulk-select-all { display: flex; align-items: center; gap: 10px; color: var(--app-text); font-weight: 750; }
.bulk-meta { color: var(--app-muted); font-size: 13px; }
.endpoint-list { display: grid; gap: 10px; }
.endpoint-row {
  display: grid; grid-template-columns: auto minmax(0, 1fr) minmax(190px, auto); align-items: center; gap: 12px; padding: 14px;
  border: 1px solid var(--app-border-soft); border-radius: 10px; background: var(--app-surface-elevated);
}
.endpoint-row--disabled { opacity: .62; }
.endpoint-row__main { display: grid; gap: 4px; min-width: 0; }
.endpoint-row__main strong { color: var(--app-text-strong); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.endpoint-row__main span, .endpoint-row__meta small { color: var(--app-muted); font-size: 12px; }
.endpoint-row__meta { display: grid; gap: 4px; justify-items: end; color: var(--app-text); font-size: 12px; font-weight: 750; }
@media (max-width: 960px) {
  .tool-hero { align-items: flex-start; padding: 24px; }
  .tool-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .bulk-layout { grid-template-columns: 1fr; }
  .bulk-panel--controls { position: static; }
  .endpoint-row { grid-template-columns: auto minmax(0, 1fr); }
  .endpoint-row__meta { grid-column: 2; justify-items: start; }
}
</style>
