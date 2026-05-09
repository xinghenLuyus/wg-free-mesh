<script setup lang="ts">
import { Monitor, RefreshRight, SwitchButton, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import { useRealtime } from '@/composables/useRealtime'
import type { ControlLogEventPayload, ControlLogRead, EndpointStatusRead, EndpointStatusUpdatedPayload, RealtimeEvent } from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const route = useRoute()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const startingWg = actions.isPending('start-wg')
const stoppingWg = actions.isPending('stop-wg')
const refreshingStatus = actions.isPending('refresh-status')
const resettingClient = actions.isPending('reset-client')
const loadingWgInfo = actions.isPending('wg-info')
const pushingConfig = actions.isPending('push-config')

const endpointStatus = shallowRef<EndpointStatusRead | null>(null)
const logs = shallowRef<ControlLogRead[]>([])
const bindingCommand = shallowRef('')
const bindingExpiresAt = shallowRef('')
const bindingBusy = shallowRef(false)
let lastRealtimeVersion = 0

const outputLogs = computed(() => logs.value.filter((log) => log.action === 'event').slice(0, 20))

async function reloadNode() {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  endpointStatus.value = await api.endpointStatus(configId, nodeId)
  logs.value = await api.endpointLogs(configId, nodeId)
}

async function refreshStatus() {
  await actions.run('refresh-status', async () => {
    const configId = String(route.params.configId)
    const nodeId = String(route.params.nodeId)
    await api.probeBatch(configId, [nodeId])
    await reloadNode()
  })
}

async function sendAction(action: string) {
  const key = action === 'start' ? 'start-wg' : action === 'stop' ? 'stop-wg' : action === 'wg_show' ? 'wg-info' : action === 'push_config' ? 'push-config' : `action-${action}`
  await actions.run(key, async () => {
    try {
      const result = await api.controlEndpoint(String(route.params.configId), String(route.params.nodeId), action)
      notify.success(result.message)
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.commandFailed'))
    }
  })
}

const needsClientInit = computed(() => {
  return endpointStatus.value?.node.node_type === 'dynamic' && !endpointStatus.value.client_state.client_initialized
})

const mqttServiceEnabled = computed(() => endpointStatus.value?.mqtt_service.enabled !== false)

function presenceLabel(state: string | undefined) {
  if (state === 'online') return t('endpointControl.presenceOnline')
  if (state === 'dropped') return t('endpointControl.presenceDropped')
  return t('endpointControl.presenceOffline')
}

function wgConfigVersionLabel(state: string | undefined) {
  if (state === 'latest') return t('endpointControl.wgConfigLatest')
  if (state === 'pending') return t('endpointControl.wgConfigPending')
  return t('endpointControl.unknown')
}

function wgRuntimeLabel(state: string | undefined) {
  if (state === 'running') return t('endpointControl.wgRunning')
  if (state === 'stopped') return t('endpointControl.wgStopped')
  return t('endpointControl.unknown')
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }
  const input = document.createElement('textarea')
  input.value = value
  input.style.position = 'fixed'
  input.style.opacity = '0'
  document.body.appendChild(input)
  input.select()
  document.execCommand('copy')
  document.body.removeChild(input)
}

async function generateBindCommand() {
  bindingBusy.value = true
  try {
    const result = await api.createClientBindCommand(String(route.params.configId), String(route.params.nodeId))
    bindingCommand.value = result.command
    bindingExpiresAt.value = result.expires_at
    await copyText(result.command)
    notify.success(t('endpointControl.bindCommandCopied'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.bindCommandFailed'))
  } finally {
    bindingBusy.value = false
  }
}

async function resetClient() {
  await actions.run('reset-client', async () => {
    try {
      await api.resetClient(String(route.params.configId), String(route.params.nodeId))
      await reloadNode()
      bindingCommand.value = ''
      bindingExpiresAt.value = ''
      notify.success(t('endpointControl.clientReset'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.clientResetFailed'))
    }
  })
}

function upsertLog(nextLog: ControlLogRead) {
  const items = [...logs.value]
  const index = items.findIndex((item) => item.id === nextLog.id)
  if (index >= 0) items[index] = nextLog
  else items.unshift(nextLog)
  logs.value = items
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .slice(0, 20)
}

const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'endpoint.status.updated') {
    const payload = event.payload as unknown as EndpointStatusUpdatedPayload
    if (payload.node_id === route.params.nodeId) {
      endpointStatus.value = payload.status
    }
  }
  if (event.type === 'control.log.created' || event.type === 'control.log.updated') {
    const payload = event.payload as unknown as ControlLogEventPayload
    if (payload.node_id === route.params.nodeId) {
      upsertLog(payload.log)
    }
  }
})

watch(
  () => [route.params.configId, route.params.nodeId],
  async () => {
    await reloadNode()
  },
)

onMounted(async () => {
  try {
    await reloadNode()
    realtime.connect()
    lastRealtimeVersion = realtime.connectionVersion.value
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.loadFailed'))
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
      await reloadNode()
    } catch {
      // Keep reconnect reconciliation silent.
    }
  },
)
</script>

<template>
  <section class="node-template">
    <div class="content-band">
      <div class="template-toolbar">
        <div>
          <h2>{{ t('endpointControl.title') }}</h2>
          <p>{{ t('endpointControl.description') }}</p>
        </div>
        <el-tag :type="realtime.connected ? 'success' : 'warning'">
          {{ realtime.connected ? t('endpointControl.realtimeOk') : t('endpointControl.realtimeDown') }}
        </el-tag>
      </div>

      <div v-if="endpointStatus && needsClientInit" class="endpoint-panels">
        <div v-if="!mqttServiceEnabled" class="endpoint-card endpoint-disabled">
          <div class="endpoint-card__title">{{ t('endpointControl.mqttDisabledTitle') }}</div>
          <p class="endpoint-init__description">{{ t('endpointControl.mqttDisabledDescription') }}</p>
        </div>
        <template v-else>
        <div class="endpoint-card endpoint-init">
          <div>
            <div class="endpoint-card__title">{{ t('endpointControl.clientInitTitle') }}</div>
            <p class="endpoint-init__description">{{ t('endpointControl.clientInitDescription') }}</p>
          </div>
          <div class="endpoint-init__steps">
            <div class="endpoint-init__step">
              <strong>{{ t('endpointControl.downloadClientStep') }}</strong>
              <span>{{ t('endpointControl.downloadClientPlaceholder') }}</span>
            </div>
            <div class="endpoint-init__step">
              <strong>{{ t('endpointControl.bindCommandStep') }}</strong>
              <span>{{ t('endpointControl.bindCommandDescription') }}</span>
              <el-button type="primary" :loading="bindingBusy" @click="generateBindCommand">
                {{ t('endpointControl.generateBindCommand') }}
              </el-button>
            </div>
          </div>
          <pre v-if="bindingCommand" class="bind-command">{{ bindingCommand }}</pre>
          <div v-if="bindingExpiresAt" class="endpoint-init__expires">
            {{ t('endpointControl.bindCommandExpiresAt', { time: formatDateTime(bindingExpiresAt) }) }}
          </div>
        </div>
        </template>
      </div>

      <div v-else-if="endpointStatus" class="endpoint-panels">
        <div class="endpoint-card">
          <div class="endpoint-card__title">{{ t('endpointControl.runtimeStatus') }}</div>
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('endpointControl.node')">{{ endpointStatus.node.name }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.clientState')">{{ presenceLabel(endpointStatus.client_state.client_presence_state) }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.clientOnline')">{{ endpointStatus.runtime.online ? t('endpointControl.online') : t('endpointControl.offline') }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.clientVersion')">{{ endpointStatus.client_state.client_version_label || t('endpointControl.unknown') }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.wgConfigVersion')">
              {{ wgConfigVersionLabel(endpointStatus.config_state.wg_config_version_state) }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.wgState')">{{ wgRuntimeLabel(endpointStatus.runtime.wg_runtime_state) }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.lastSeen')">{{ formatDateTime(endpointStatus.runtime.last_seen) }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.lastHeartbeat')">{{ formatDateTime(endpointStatus.client_state.last_heartbeat_at) }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.lastDetect')">{{ formatDateTime(endpointStatus.runtime.last_probe_ack_at) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="endpoint-card">
          <div class="endpoint-card__title">{{ t('endpointControl.remoteControl') }}</div>
          <div v-if="!mqttServiceEnabled" class="endpoint-disabled__message">
            {{ t('endpointControl.mqttDisabledDescription') }}
          </div>
          <div class="endpoint-controls">
            <el-button :icon="VideoPlay" :loading="startingWg" :disabled="!mqttServiceEnabled" @click="sendAction('start')">{{ t('endpointControl.startWg') }}</el-button>
            <el-button :icon="VideoPause" :loading="stoppingWg" :disabled="!mqttServiceEnabled" @click="sendAction('stop')">{{ t('endpointControl.stopWg') }}</el-button>
            <el-button :icon="RefreshRight" :loading="pushingConfig" :disabled="!mqttServiceEnabled" @click="sendAction('push_config')">{{ t('endpointControl.syncConfig') }}</el-button>
            <el-button :icon="Monitor" :loading="loadingWgInfo" :disabled="!mqttServiceEnabled" @click="sendAction('wg_show')">{{ t('endpointControl.wgInfo') }}</el-button>
            <el-button plain :icon="RefreshRight" :loading="refreshingStatus" @click="refreshStatus">{{ t('endpointControl.refreshStatus') }}</el-button>
            <el-button type="danger" plain :icon="SwitchButton" :loading="resettingClient" :disabled="!mqttServiceEnabled" @click="resetClient">{{ t('endpointControl.resetClient') }}</el-button>
          </div>
        </div>

        <div class="endpoint-card">
          <div class="endpoint-card__title">{{ t('endpointControl.cliOutput') }}</div>
          <div v-if="outputLogs.length" class="endpoint-output-box">
            <div v-for="log in outputLogs" :key="log.id" class="endpoint-output-box__entry">
              <div class="endpoint-output-box__time">{{ formatDateTime(log.created_at) }}</div>
              <pre class="endpoint-output-box__text">{{ log.detail || log.summary }}</pre>
            </div>
          </div>
          <div v-else class="empty-state">{{ t('endpointControl.noLogs') }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.node-template { display: grid; gap: 20px; }
.template-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.template-toolbar h2 { margin: 0; color: var(--app-text); font-size: 22px; }
.template-toolbar p { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.endpoint-panels { display: grid; gap: 20px; }
.endpoint-card { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-elevated); box-shadow: var(--app-shadow-sm); }
.endpoint-card__title { color: var(--app-text-strong); font-size: 17px; font-weight: 750; }
.endpoint-controls { display: flex; flex-wrap: wrap; gap: 10px; }
.endpoint-init { gap: 18px; }
.endpoint-init__description { margin: 8px 0 0; color: var(--app-muted); line-height: 1.6; }
.endpoint-init__steps { display: grid; gap: 12px; }
.endpoint-init__step { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); }
.endpoint-init__step strong { color: var(--app-text-strong); }
.endpoint-init__step span, .endpoint-init__expires { color: var(--app-muted); }
.endpoint-disabled__message { color: var(--app-danger-text); line-height: 1.6; }
.endpoint-output-box {
  display: grid;
  overflow: hidden;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}
.endpoint-output-box__entry {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--app-border-soft);
}
.endpoint-output-box__entry:last-child { border-bottom: 0; }
.endpoint-output-box__time {
  color: var(--app-faint);
  font-size: 12px;
  font-weight: 650;
}
.endpoint-output-box__text {
  margin: 0;
  color: var(--app-text-strong);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--app-font-mono, ui-monospace, SFMono-Regular, Consolas, monospace);
  line-height: 1.55;
}
.bind-command { margin: 0; padding: 14px; border: 1px solid var(--app-border-strong); border-radius: 8px; overflow-x: auto; background: var(--app-surface-sunken); color: var(--app-text-strong); white-space: pre-wrap; word-break: break-all; }
.empty-state { display: grid; place-items: center; min-height: 120px; border: 1px dashed var(--app-border-strong); border-radius: 8px; color: var(--app-muted); }
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } }
</style>
