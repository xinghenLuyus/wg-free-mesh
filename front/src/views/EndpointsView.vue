<script setup lang="ts">
import { RefreshRight, SwitchButton, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ControlLogEventPayload, ControlLogRead, EndpointStatusRead, EndpointStatusUpdatedPayload, RealtimeEvent } from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const route = useRoute()
const { t } = useI18n()

const endpointStatus = shallowRef<EndpointStatusRead | null>(null)
const logs = shallowRef<ControlLogRead[]>([])
const bindingCommand = shallowRef('')
const bindingExpiresAt = shallowRef('')
const bindingBusy = shallowRef(false)

const outputLogs = computed(() => logs.value.filter((log) => log.action === 'event'))

async function reloadNode() {
  const configId = String(route.params.configId)
  const nodeId = String(route.params.nodeId)
  endpointStatus.value = await api.endpointStatus(configId, nodeId)
  logs.value = await api.endpointLogs(configId, nodeId)
}

async function sendAction(action: string) {
  try {
    const result = await api.controlEndpoint(String(route.params.configId), String(route.params.nodeId), action)
    notify.success(result.message)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.commandFailed'))
  }
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
  try {
    await api.resetClient(String(route.params.configId), String(route.params.nodeId))
    await reloadNode()
    bindingCommand.value = ''
    bindingExpiresAt.value = ''
    notify.success(t('endpointControl.clientReset'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.clientResetFailed'))
  }
}

function upsertLog(nextLog: ControlLogRead) {
  const items = [...logs.value]
  const index = items.findIndex((item) => item.id === nextLog.id)
  if (index >= 0) items[index] = nextLog
  else items.unshift(nextLog)
  logs.value = items.sort((left, right) => right.created_at.localeCompare(left.created_at))
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
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('endpointControl.loadFailed'))
  }
})
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
            <el-descriptions-item :label="t('endpointControl.wgState')">{{ endpointStatus.runtime.wg_runtime_state }}</el-descriptions-item>
            <el-descriptions-item :label="t('endpointControl.lastSeen')">{{ formatDateTime(endpointStatus.runtime.last_seen) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="endpoint-card">
          <div class="endpoint-card__title">{{ t('endpointControl.remoteControl') }}</div>
          <div v-if="!mqttServiceEnabled" class="endpoint-disabled__message">
            {{ t('endpointControl.mqttDisabledDescription') }}
          </div>
          <div class="endpoint-controls">
            <el-button :icon="VideoPlay" :disabled="!mqttServiceEnabled" @click="sendAction('start')">{{ t('endpointControl.startWg') }}</el-button>
            <el-button :icon="VideoPause" :disabled="!mqttServiceEnabled" @click="sendAction('stop')">{{ t('endpointControl.stopWg') }}</el-button>
            <el-button plain :icon="RefreshRight" @click="reloadNode">{{ t('endpointControl.refreshStatus') }}</el-button>
            <el-button type="danger" plain :icon="SwitchButton" :disabled="!mqttServiceEnabled" @click="resetClient">{{ t('endpointControl.resetClient') }}</el-button>
          </div>
        </div>

        <div class="endpoint-card">
          <div class="endpoint-card__title">{{ t('endpointControl.cliOutput') }}</div>
          <el-timeline>
            <el-timeline-item v-for="log in outputLogs" :key="log.id" :timestamp="formatDateTime(log.created_at)">
              <div class="endpoint-log-line">{{ log.detail || log.summary }}</div>
            </el-timeline-item>
          </el-timeline>
          <div v-if="!outputLogs.length" class="empty-state">{{ t('endpointControl.noLogs') }}</div>
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
.endpoint-log-line { color: var(--app-text-strong); white-space: pre-wrap; word-break: break-word; font-family: var(--app-font-mono, ui-monospace, SFMono-Regular, Consolas, monospace); }
.bind-command { margin: 0; padding: 14px; border: 1px solid var(--app-border-strong); border-radius: 8px; overflow-x: auto; background: var(--app-surface-sunken); color: var(--app-text-strong); white-space: pre-wrap; word-break: break-all; }
.empty-state { display: grid; place-items: center; min-height: 120px; border: 1px dashed var(--app-border-strong); border-radius: 8px; color: var(--app-muted); }
@media (max-width: 860px) { .template-toolbar { flex-direction: column; align-items: stretch; } }
</style>
