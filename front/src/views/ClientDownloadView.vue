<script setup lang="ts">
import { ArrowLeft, Download, Finished, SetUp } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { ClientDownloadOptionsRead } from '@/types/api'
import { notify } from '@/utils/notify'

const { t } = useI18n()
const router = useRouter()

const options = shallowRef<ClientDownloadOptionsRead | null>(null)
const source = shallowRef('local_build')
const goos = shallowRef('windows')
const goarch = shallowRef('amd64')
const loading = shallowRef(false)
const building = shallowRef(false)
const loadError = shallowRef('')
const statusState = shallowRef<'idle' | 'building' | 'downloading' | 'done' | 'failed'>('idle')

const selectedSource = computed(() => options.value?.sources.find((item) => item.value === source.value))
const sourceAvailable = computed(() => selectedSource.value?.available !== false)
const sourceLabel = computed(() => translateDownloadOption(selectedSource.value?.value, selectedSource.value?.label || source.value))
const statusTitle = computed(() => t(`tools.clientDownload.status.${statusState.value}.title`))
const statusDescription = computed(() => t(`tools.clientDownload.status.${statusState.value}.description`))

function translateDownloadOption(value: string | undefined, fallback: string) {
  if (value === 'local_build') return t('tools.clientDownload.localBuild')
  if (value === 'github_release') return t('tools.clientDownload.githubRelease')
  return fallback
}

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

async function loadOptions() {
  loading.value = true
  loadError.value = ''
  try {
    const nextOptions = await api.clientDownloadOptions()
    options.value = nextOptions
    source.value = nextOptions.defaults.source
    goos.value = nextOptions.defaults.goos
    goarch.value = nextOptions.defaults.goarch
  } catch (error) {
    loadError.value = error instanceof ApiClientError ? error.message : t('tools.clientDownload.loadFailed')
    notify.error(loadError.value)
  } finally {
    loading.value = false
  }
}

async function generateArtifact() {
  if (!sourceAvailable.value) return
  const requestedSource = source.value
  const requestedGoos = goos.value
  const requestedGoarch = goarch.value
  building.value = true
  statusState.value = 'building'
  try {
    const nextArtifact = await api.buildClientArtifact({
      source: requestedSource,
      goos: requestedGoos,
      goarch: requestedGoarch,
    })
    if (source.value !== requestedSource || goos.value !== requestedGoos || goarch.value !== requestedGoarch) return
    statusState.value = 'downloading'
    const blob = await api.downloadClientArtifact(nextArtifact.artifact_id)
    if (source.value !== requestedSource || goos.value !== requestedGoos || goarch.value !== requestedGoarch) return
    saveBlob(blob, nextArtifact.filename)
    statusState.value = 'done'
    notify.success(t('tools.clientDownload.downloadStarted'))
  } catch (error) {
    statusState.value = 'failed'
    notify.error(error instanceof ApiClientError ? error.message : t('tools.clientDownload.buildFailed'))
  } finally {
    building.value = false
  }
}

function backToDownloadTools() {
  void router.push('/tools/download')
}

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
          <h1>{{ t('tools.clientDownload.title') }}</h1>
          <p>{{ t('tools.clientDownload.description') }}</p>
        </div>
      </div>
      <el-icon><Download /></el-icon>
    </div>

    <div v-if="loading" class="content-band view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError" class="content-band view-feedback view-feedback--error">{{ loadError }}</div>
    <div v-else-if="options" class="tool-grid">
      <article class="tool-panel">
        <div class="tool-panel__head">
          <el-icon><SetUp /></el-icon>
          <div>
            <h2>{{ t('tools.clientDownload.localBuild') }}</h2>
            <p>{{ t('tools.clientDownload.requirement') }}</p>
          </div>
        </div>

        <el-form label-position="top" class="tool-form">
          <el-form-item :label="t('tools.clientDownload.source')">
            <el-select v-model="source">
              <el-option
                v-for="item in options.sources"
                :key="item.value"
                :label="item.available === false ? `${translateDownloadOption(item.value, item.label)} · ${t('tools.clientDownload.unavailable')}` : translateDownloadOption(item.value, item.label)"
                :value="item.value"
                :disabled="item.available === false"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tools.clientDownload.system')">
            <el-segmented v-model="goos" :options="options.systems" />
          </el-form-item>
          <el-form-item :label="t('tools.clientDownload.architecture')">
            <el-segmented v-model="goarch" :options="options.architectures" />
          </el-form-item>
        </el-form>

        <el-button type="primary" :icon="SetUp" :loading="building" :disabled="!sourceAvailable" @click="generateArtifact">
          {{ t('tools.clientDownload.buildAndDownload') }}
        </el-button>
      </article>

      <aside class="tool-panel tool-panel--summary">
        <div class="tool-panel__head">
          <el-icon><Finished /></el-icon>
          <div>
            <h2>{{ statusTitle }}</h2>
            <p>{{ statusDescription }}</p>
          </div>
        </div>
        <dl class="tool-summary">
          <div>
            <dt>{{ t('tools.clientDownload.source') }}</dt>
            <dd>{{ sourceLabel }}</dd>
          </div>
          <div>
            <dt>{{ t('tools.clientDownload.system') }}</dt>
            <dd>{{ goos }}</dd>
          </div>
          <div>
            <dt>{{ t('tools.clientDownload.architecture') }}</dt>
            <dd>{{ goarch }}</dd>
          </div>
          <div>
            <dt>{{ t('tools.clientDownload.version') }}</dt>
            <dd>{{ options.version }}</dd>
          </div>
        </dl>
      </aside>
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
.tool-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr); gap: 18px; }
.tool-panel { display: grid; gap: 20px; padding: 24px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.tool-panel--summary { align-self: start; }
.tool-panel__head { display: flex; gap: 14px; align-items: flex-start; }
.tool-panel__head > .el-icon { flex: 0 0 auto; width: 42px; height: 42px; border-radius: 10px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 22px; }
.tool-panel__head h2 { margin: 0; color: var(--app-text-strong); font-size: 18px; letter-spacing: 0; }
.tool-panel__head p { margin: 6px 0 0; color: var(--app-muted); font-size: 13px; }
.tool-form { display: grid; gap: 4px; }
.tool-form :deep(.el-select), .tool-form :deep(.el-segmented) { width: 100%; }
.tool-summary { display: grid; gap: 14px; margin: 0; }
.tool-summary div { display: grid; gap: 5px; padding-bottom: 12px; border-bottom: 1px solid var(--app-border-soft); }
.tool-summary dt { color: var(--app-faint); font-size: 12px; font-weight: 800; }
.tool-summary dd { margin: 0; color: var(--app-text-strong); font-weight: 750; overflow-wrap: anywhere; }
@media (max-width: 960px) {
  .tool-hero { align-items: flex-start; padding: 24px; }
  .tool-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .tool-grid { grid-template-columns: 1fr; }
}
</style>
