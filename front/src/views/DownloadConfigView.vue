<script setup lang="ts">
import { CopyDocument, Download, Link, PictureFilled } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { DownloadPackageRead, NodeApplyUpdatedPayload, RealtimeEvent } from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const route = useRoute()
const { t } = useI18n()

const downloadPackage = shallowRef<DownloadPackageRead | null>(null)
const qrCodeDataUrl = shallowRef('')
const qrExpanded = shallowRef(false)
const loading = shallowRef(false)
const loadError = shallowRef('')
const generatingLink = shallowRef(false)
const generatingShell = shallowRef(false)
const downloadingConf = shallowRef(false)
const downloadUrl = shallowRef('')
const shellCommand = shallowRef('')
let loadTicket = 0
const tokenCache = reactive({
  downloadUrl: '',
  shellUrl: '',
  linkExpiresAt: '',
  shellExpiresAt: '',
})

const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type !== 'node.apply.updated') return
  const payload = event.payload as unknown as NodeApplyUpdatedPayload
  if (payload.config_id !== String(route.params.configId) || payload.node_id !== String(route.params.nodeId)) return
  void loadDownloadPackage()
})

const qrHelpText = computed(() =>
  downloadPackage.value?.content.trim()
    ? t('download.qrDescription')
    : t('download.qrEmpty'),
)
const linkExpiresAtText = computed(() => formatDateTime(tokenCache.linkExpiresAt, ''))
const shellExpiresAtText = computed(() => formatDateTime(tokenCache.shellExpiresAt, ''))

async function generateQrCode(content: string) {
  if (!content.trim()) {
    qrCodeDataUrl.value = ''
    return
  }
  qrCodeDataUrl.value = await QRCode.toDataURL(content, {
    errorCorrectionLevel: 'M',
    margin: 1,
    width: 320,
  })
}

function resetGeneratedOutputs() {
  tokenCache.downloadUrl = ''
  tokenCache.shellUrl = ''
  tokenCache.linkExpiresAt = ''
  tokenCache.shellExpiresAt = ''
  downloadUrl.value = ''
  shellCommand.value = ''
}

async function issueDownloadUrl(target: 'link' | 'shell' | 'browser') {
  if (!downloadPackage.value) return ''
  const token = await api.createDownloadToken(String(route.params.configId), String(route.params.nodeId))
  const nextUrl = new URL(token.download_path, window.location.origin).toString()
  if (target === 'link') {
    tokenCache.downloadUrl = nextUrl
    tokenCache.linkExpiresAt = token.expires_at
    downloadUrl.value = nextUrl
  } else if (target === 'shell') {
    tokenCache.shellUrl = nextUrl
    tokenCache.shellExpiresAt = token.expires_at
  }
  return nextUrl
}

async function loadDownloadPackage() {
  const ticket = ++loadTicket
  loading.value = true
  loadError.value = ''
  try {
    const nextPackage = await api.downloadPackage(String(route.params.configId), String(route.params.nodeId))
    if (ticket !== loadTicket) return
    downloadPackage.value = nextPackage
    resetGeneratedOutputs()
    if (!qrExpanded.value) qrCodeDataUrl.value = ''
  } catch (error) {
    if (ticket !== loadTicket) return
    loadError.value = error instanceof ApiClientError ? error.message : t('download.loadFailed')
    throw error
  } finally {
    if (ticket === loadTicket) loading.value = false
  }
}

async function copyText(value: string, successMessage: string) {
  if (!value) {
    notify.error(t('download.noCopyContent'))
    return
  }
  try {
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(value)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = value
      textarea.setAttribute('readonly', 'true')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      textarea.style.pointerEvents = 'none'
      document.body.appendChild(textarea)
      textarea.select()
      textarea.setSelectionRange(0, textarea.value.length)
      const copied = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (!copied) throw new Error('copy failed')
    }
    notify.success(successMessage)
  } catch {
    notify.error(t('download.copyFailed'))
  }
}

async function createAndCopyDownloadUrl() {
  if (!downloadPackage.value) return
  generatingLink.value = true
  try {
    const nextUrl = await issueDownloadUrl('link')
    await copyText(nextUrl, t('download.linkCopied'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('download.linkFailed'))
  } finally {
    generatingLink.value = false
  }
}

async function downloadConfFile() {
  if (!downloadPackage.value) return
  downloadingConf.value = true
  try {
    const nextUrl = await issueDownloadUrl('browser')
    window.location.assign(nextUrl)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('download.linkFailed'))
  } finally {
    downloadingConf.value = false
  }
}

async function createAndCopyShellCommand() {
  if (!downloadPackage.value) return
  generatingShell.value = true
  try {
    const nextUrl = await issueDownloadUrl('shell')
    shellCommand.value = [
      'sudo mkdir -p /etc/wireguard',
      `sudo curl -fsSL "${nextUrl}" -o "/etc/wireguard/${downloadPackage.value.filename}"`,
      `sudo chmod 600 "/etc/wireguard/${downloadPackage.value.filename}"`,
    ].join(' && ')
    await copyText(shellCommand.value, t('download.shellCopied'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('download.shellFailed'))
  } finally {
    generatingShell.value = false
  }
}

async function toggleQrPanel() {
  qrExpanded.value = !qrExpanded.value
  if (qrExpanded.value && !qrCodeDataUrl.value && downloadPackage.value?.content.trim()) {
    try {
      await generateQrCode(downloadPackage.value.content)
    } catch {
      notify.error(t('download.qrFailed'))
    }
  }
}

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    try {
      await loadDownloadPackage()
    } catch {
      notify.error(loadError.value || t('download.loadFailed'))
    }
  },
)

onMounted(async () => {
  try {
    await loadDownloadPackage()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('download.loadFailed'))
  }
})
</script>

<template>
  <section class="node-template">
    <div v-if="loading && !downloadPackage" class="content-band view-feedback view-feedback--silent" aria-hidden="true"></div>
    <div v-else-if="loadError && !downloadPackage" class="content-band view-feedback view-feedback--error">{{ loadError }}</div>
    <div v-else-if="downloadPackage" class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>{{ t('download.title') }}</h2>
          <p>{{ t('download.description') }}</p>
        </div>
        <div class="template-toolbar__actions">
          <el-button type="primary" :icon="Download" :loading="downloadingConf" @click="downloadConfFile">{{ t('download.confDownload') }}</el-button>
        </div>
      </div>

      <div class="download-grid">
        <article class="download-card">
          <div class="download-card__head">
            <div class="download-card__title">
              <el-icon><Link /></el-icon>
              <div>
                <strong>{{ t('download.httpTitle') }}</strong>
              </div>
            </div>
            <el-button class="download-action" plain :icon="Link" :loading="generatingLink" @click="createAndCopyDownloadUrl">
              {{ t('download.httpAction') }}
            </el-button>
          </div>
          <p class="download-card__description">{{ t('download.httpDescription') }}</p>
          <el-input
            v-if="downloadUrl"
            :model-value="downloadUrl"
            readonly
            class="download-output"
            type="textarea"
            :rows="3"
            resize="none"
          />
          <p v-if="tokenCache.linkExpiresAt" class="download-card__meta">{{ t('download.linkExpiresAt', { time: linkExpiresAtText }) }}</p>
        </article>

        <article class="download-card">
          <div class="download-card__head">
            <div class="download-card__title">
              <el-icon><PictureFilled /></el-icon>
              <div>
                <strong>{{ t('download.qrTitle') }}</strong>
              </div>
            </div>
            <el-button class="download-action" plain :icon="PictureFilled" @click="toggleQrPanel">
              {{ qrExpanded ? t('download.qrClose') : t('download.qrOpen') }}
            </el-button>
          </div>
          <p class="download-card__description">{{ qrHelpText }}</p>
          <div v-if="qrExpanded" class="qr-panel">
            <img v-if="qrCodeDataUrl" :src="qrCodeDataUrl" alt="WireGuard config QR code" class="qr-panel__image" />
            <div v-else class="qr-panel__empty">{{ t('download.qrEmpty') }}</div>
          </div>
        </article>

        <article class="download-card">
          <div class="download-card__head">
            <div class="download-card__title">
              <el-icon><CopyDocument /></el-icon>
              <div>
                <strong>{{ t('download.shellTitle') }}</strong>
              </div>
            </div>
            <el-button class="download-action" plain :icon="CopyDocument" :loading="generatingShell" @click="createAndCopyShellCommand">
              {{ t('download.shellAction') }}
            </el-button>
          </div>
          <p class="download-card__description">{{ t('download.shellDescription') }}</p>
          <el-input
            v-if="shellCommand"
            type="textarea"
            :rows="4"
            resize="none"
            readonly
            :model-value="shellCommand"
            class="download-output"
          />
          <p v-if="tokenCache.shellExpiresAt" class="download-card__meta">{{ t('download.shellExpiresAt', { time: shellExpiresAtText }) }}</p>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.node-template { display: grid; gap: 20px; }
.view-feedback { color: var(--app-muted); }
.view-feedback--silent { min-height: 140px; color: transparent; }
.view-feedback--error { color: var(--app-danger-text); }
.template-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.template-toolbar h2 { margin: 0; color: var(--app-text); font-size: 22px; }
.template-toolbar p { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.template-toolbar__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.download-grid { display: grid; gap: 16px; }
.download-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-sm);
}
.download-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}
.download-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.download-card__title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.download-card__title .el-icon {
  margin-top: 2px;
  color: var(--app-primary);
  font-size: 18px;
}
.download-card__title strong,
.download-card__title span {
  display: block;
}
.download-card__title strong {
  color: var(--app-text);
  font-size: 17px;
}
.download-card__title span {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 13px;
}
.download-card__description {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.6;
}
.download-card__meta {
  margin: -4px 0 0;
  color: var(--app-faint);
  font-size: 12px;
}
.download-action {
  --el-button-text-color: var(--app-text-strong);
  --el-button-bg-color: var(--app-surface-elevated);
  --el-button-border-color: var(--app-border-soft);
  --el-button-hover-text-color: var(--app-text-strong);
  --el-button-hover-bg-color: var(--app-surface-sunken);
  --el-button-hover-border-color: var(--app-border-accent);
  --el-button-active-text-color: var(--app-text-strong);
  --el-button-active-bg-color: var(--app-surface-selected);
  --el-button-active-border-color: var(--app-border-accent);
  font-weight: 700;
  box-shadow: none;
}
.download-output :deep(.el-textarea__inner) {
  min-height: 96px;
  border-color: var(--app-border-soft);
  background: var(--app-surface-sunken);
  color: var(--app-text-strong);
  font-size: 13px;
  line-height: 1.7;
  font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  box-shadow: none;
}
.qr-panel {
  display: grid;
  place-items: center;
  min-height: 280px;
  padding: 16px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}
.qr-panel__image {
  width: min(100%, 320px);
  height: auto;
  border-radius: 8px;
}
.qr-panel__empty {
  color: var(--app-muted);
  text-align: center;
}
@media (max-width: 860px) {
  .template-toolbar,
  .download-card__head {
    flex-direction: column;
    align-items: stretch;
  }
  .template-toolbar__actions { justify-content: flex-start; }
}
</style>
