<script setup lang="ts">
import { Check, Connection, Delete, Download, Edit, Files, Lock, Monitor, Plus, RefreshLeft, Setting, Upload } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import type { FormInstance, FormItemRule, FormRules } from 'element-plus'
import { computed, nextTick, onMounted, reactive, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import { useRealtime } from '@/composables/useRealtime'
import { SUPPORTED_LOCALES } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type {
  AppLocale,
  AppThemeMode,
  MqttSettingsUpdatedPayload,
  RealtimeEvent,
  SnapshotListUpdatedPayload,
  SnapshotRead,
} from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { requiredTextRule } from '@/utils/formRules'
import { notify } from '@/utils/notify'

const { t } = useI18n()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()
const actions = useAsyncActionGroup()
const savingPassword = actions.isPending('save-password')
const savingMqtt = actions.isPending('save-mqtt')
const resettingMqtt = actions.isPending('reset-mqtt')
const testingMqtt = actions.isPending('test-mqtt')
const creatingSnapshot = actions.isPending('create-snapshot')
const importingSnapshot = actions.isPending('import-snapshot')
const restoringSnapshot = shallowRef(false)
const mqttServicesEnabled = shallowRef(true)
const mqttForm = reactive({
  host: '',
  port: 8883,
  tls: true,
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
})
const selectedLocale = shallowRef<AppLocale>(preferencesStore.locale)
const selectedThemeMode = shallowRef<AppThemeMode>(preferencesStore.themeMode)
const mqttFormRef = shallowRef<FormInstance>()
const passwordFormRef = shallowRef<FormInstance>()
const passwordResetting = shallowRef(false)
const snapshotImportInput = shallowRef<HTMLInputElement | null>(null)
const mqttRules: FormRules<typeof mqttForm> = {
  host: [{
    trigger: ['blur', 'change'],
    validator: (_rule, value, callback) => {
      if (typeof value !== 'string' || !value.trim()) {
        callback(new Error(t('validation.required', { field: t('fields.host') })))
        return
      }
      callback()
    },
  }],
}

function quietPasswordRule(validator: FormItemRule['validator']): FormItemRule {
  return {
    trigger: ['blur', 'change'],
    validator: (rule, value, callback, source, options) => {
      if (passwordResetting.value) {
        callback()
        return
      }
      validator?.(rule, value, callback, source, options)
    },
  }
}

const passwordRules: FormRules<typeof passwordForm> = {
  current_password: [
    quietPasswordRule((_rule, value, callback) => {
      if (typeof value !== 'string' || !value.trim()) {
        callback(new Error(t('validation.required', { field: t('fields.currentPassword') })))
        return
      }
      callback()
    }),
  ],
  new_password: [
    quietPasswordRule((_rule, value, callback) => {
      if (typeof value !== 'string' || value.trim().length < 6) {
        callback(new Error(t('validation.minLength', { field: t('fields.newPassword'), min: 6 })))
        return
      }
      callback()
    }),
  ],
}

const snapshots = shallowRef<SnapshotRead[]>([])
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'snapshot.list.updated') {
    snapshots.value = (event.payload as unknown as SnapshotListUpdatedPayload).snapshots
  }
  if (event.type === 'settings.mqtt.updated') {
    Object.assign(mqttForm, (event.payload as unknown as MqttSettingsUpdatedPayload).mqtt)
  }
})

async function load() {
  const uiSettings = await preferencesStore.load()
  const health = await api.health()
  selectedLocale.value = uiSettings.locale
  selectedThemeMode.value = uiSettings.theme_mode
  mqttServicesEnabled.value = health.mqtt_services_enabled
  if (mqttServicesEnabled.value) {
    Object.assign(mqttForm, await api.mqttSettings())
  }
  snapshots.value = await api.snapshots()
}

const themeOptions: Array<{ value: AppThemeMode; labelKey: string }> = [
  { value: 'system', labelKey: 'theme.system' },
  { value: 'light', labelKey: 'theme.light' },
  { value: 'dark', labelKey: 'theme.dark' },
]

const themeSegmentedOptions = computed(() =>
  themeOptions.map((option) => ({ label: t(option.labelKey), value: option.value })),
)

function mqttTestMessage(success: boolean, latencyMs: number) {
  return t(success ? 'settings.connectionSuccessWithLatency' : 'settings.connectionFailedWithLatency', {
    latency: latencyMs,
  })
}

function localeLabel(locale: AppLocale | string) {
  return locale === 'en-US' ? t('locale.enUS') : t('locale.zhCN')
}

async function saveLocale(locale: AppLocale) {
  try {
    const settings = await preferencesStore.save({ locale })
    selectedLocale.value = settings.locale
    notify.success(t('locale.saved'))
  } catch (error) {
    selectedLocale.value = preferencesStore.locale
    notify.error(error instanceof ApiClientError ? error.message : t('locale.saveFailed'))
  }
}

async function saveThemeMode(themeMode: AppThemeMode) {
  try {
    const settings = await preferencesStore.save({ theme_mode: themeMode })
    selectedThemeMode.value = settings.theme_mode
    notify.success(t('theme.saved'))
  } catch (error) {
    selectedThemeMode.value = preferencesStore.themeMode
    notify.error(error instanceof ApiClientError ? error.message : t('theme.saveFailed'))
  }
}

async function saveMqtt() {
  await actions.run('save-mqtt', async () => {
    const valid = await mqttFormRef.value?.validate().catch(() => false)
    if (!valid) return
    try {
      Object.assign(mqttForm, await api.updateMqttSettings({ ...mqttForm }))
      notify.success(t('settings.mqttSaved'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('settings.mqttSaveFailed'))
    }
  })
}

async function resetMqtt() {
  await actions.run('reset-mqtt', async () => {
    try {
      Object.assign(mqttForm, await api.resetMqttSettings())
      mqttFormRef.value?.clearValidate()
      notify.success(t('settings.mqttReset'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('settings.mqttResetFailed'))
    }
  })
}

async function testMqtt() {
  await actions.run('test-mqtt', async () => {
    const valid = await mqttFormRef.value?.validate().catch(() => false)
    if (!valid) return
    try {
      const result = await api.testMqttSettings({ ...mqttForm })
      const message = mqttTestMessage(result.success, result.latency_ms)
      if (result.success) {
        notify.success(message)
      } else {
        notify.error(message)
      }
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('settings.mqttTestFailed'))
    }
  })
}

async function savePassword() {
  await actions.run('save-password', async () => {
    const valid = await passwordFormRef.value?.validate().catch(() => false)
    if (!valid) return
    try {
      await authStore.changePassword(passwordForm.current_password, passwordForm.new_password)
      passwordResetting.value = true
      passwordForm.current_password = ''
      passwordForm.new_password = ''
      await nextTick()
      passwordFormRef.value?.clearValidate()
      window.setTimeout(() => {
        passwordResetting.value = false
        passwordFormRef.value?.clearValidate()
      }, 0)
      notify.success(t('settings.passwordSaved'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('settings.passwordFailed'))
    }
  })
}

async function createSnapshot() {
  const note = await promptSnapshotNote('')
  if (note === null) return
  const password = await promptSnapshotPassword(t('settings.snapshotCreatePasswordPrompt'))
  if (password === null) return
  await actions.run('create-snapshot', async () => {
    try {
      await api.createSnapshot(note, password)
      notify.success(t('settings.snapshotCreated'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('settings.snapshotCreateFailed'))
    }
  })
}

async function editSnapshotNote(snapshot: SnapshotRead) {
  const note = await promptSnapshotNote(snapshot.note)
  if (note === null) return
  try {
    await api.updateSnapshotNote(snapshot.id, note)
    notify.success(t('settings.snapshotNoteSaved'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('settings.snapshotNoteSaveFailed'))
  }
}

async function exportSnapshot(snapshot: SnapshotRead) {
  try {
    const blob = await api.exportSnapshot(snapshot.id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = snapshot.name
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    notify.success(t('settings.snapshotExported'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('settings.snapshotExportFailed'))
  }
}

function openSnapshotImport() {
  snapshotImportInput.value?.click()
}

async function handleSnapshotImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  await actions.run('import-snapshot', async () => {
    try {
      await api.importSnapshot(file)
      notify.success(t('settings.snapshotImported'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('settings.snapshotImportFailed'))
    }
  })
}

async function restoreSnapshot(snapshotId: string) {
  const password = await promptSnapshotPassword(t('settings.snapshotRestorePasswordPrompt'))
  if (password === null) return
  restoringSnapshot.value = true
  try {
    await api.restoreSnapshot(snapshotId, password)
    notify.success(t('settings.snapshotRestored'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('settings.snapshotRestoreFailed'))
  } finally {
    restoringSnapshot.value = false
  }
}

async function removeSnapshot(snapshotId: string) {
  try {
    await api.deleteSnapshot(snapshotId)
    notify.success(t('settings.snapshotDeleted'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('settings.snapshotDeleteFailed'))
  }
}

function isDialogCancel(error: unknown) {
  if (typeof error === 'string') {
    return error === 'cancel' || error === 'close'
  }
  if (typeof error === 'object' && error !== null && 'action' in error) {
    const action = String((error as { action?: unknown }).action || '')
    return action === 'cancel' || action === 'close'
  }
  return false
}

async function promptSnapshotNote(initialValue: string) {
  try {
    const result = await ElMessageBox.prompt(
      t('settings.snapshotNotePrompt'),
      t('settings.snapshotNoteTitle'),
      {
        inputType: 'textarea',
        inputValue: initialValue,
        inputPlaceholder: t('settings.snapshotNotePlaceholder'),
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      },
    )
    return result.value.trim()
  } catch (error) {
    if (isDialogCancel(error)) {
      return null
    }
    throw error
  }
}

async function promptSnapshotPassword(prompt: string) {
  try {
    const result = await ElMessageBox.prompt(prompt, t('settings.snapshotPasswordTitle'), {
      inputType: 'password',
      inputPattern: /.+/,
      inputErrorMessage: t('validation.required', { field: t('fields.currentPassword') }),
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    return result.value
  } catch (error) {
    if (isDialogCancel(error)) {
      return null
    }
    throw error
  }
}

onMounted(async () => {
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('settings.loadFailed'))
  }
})
</script>

<template>
  <section class="settings-hero">
    <div>
      <span class="settings-hero__eyebrow">{{ t('settings.eyebrow') }}</span>
      <h1 class="page-title">{{ t('settings.title') }}</h1>
      <p class="page-description">{{ t('settings.description') }}</p>
    </div>
  </section>

  <section class="settings-grid">
    <article class="settings-card settings-card--language">
      <div class="settings-card__head">
        <span class="settings-card__icon"><el-icon><Setting /></el-icon></span>
        <div>
          <h2>{{ t('settings.languageTitle') }}</h2>
          <p>{{ t('settings.languageDescription') }}</p>
        </div>
      </div>
      <el-form class="settings-form settings-form--compact" label-position="top">
        <el-form-item :label="t('locale.label')" required>
          <el-select v-model="selectedLocale" :loading="preferencesStore.loading" @change="saveLocale">
            <el-option
              v-for="locale in SUPPORTED_LOCALES"
              :key="locale.code"
              :label="localeLabel(locale.code)"
              :value="locale.code"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </article>

    <article class="settings-card settings-card--language">
      <div class="settings-card__head">
        <span class="settings-card__icon"><el-icon><Monitor /></el-icon></span>
        <div>
          <h2>{{ t('settings.themeTitle') }}</h2>
          <p>{{ t('settings.themeDescription') }}</p>
        </div>
      </div>
      <el-form class="settings-form settings-form--compact" label-position="top">
        <el-form-item :label="t('theme.label')" required>
          <el-segmented
            v-model="selectedThemeMode"
            class="theme-mode-segmented"
            :disabled="preferencesStore.loading"
            :options="themeSegmentedOptions"
            @change="saveThemeMode"
          />
        </el-form-item>
      </el-form>
    </article>

    <article class="settings-card settings-card--password">
      <div class="settings-card__head">
        <span class="settings-card__icon"><el-icon><Lock /></el-icon></span>
        <div>
          <h2>{{ t('settings.passwordTitle') }}</h2>
          <p>{{ t('settings.passwordDescription') }}</p>
        </div>
      </div>

      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        class="settings-form"
        label-position="top"
        autocomplete="off"
      >
        <input
          class="credential-autocomplete-anchor"
          type="text"
          name="username"
          autocomplete="username"
          :value="authStore.state?.username || 'admin'"
          readonly
          tabindex="-1"
          aria-hidden="true"
        />
        <el-form-item :label="t('fields.currentPassword')" prop="current_password" required>
          <el-input
            v-model="passwordForm.current_password"
            type="password"
            show-password
            name="current-password"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item :label="t('fields.newPassword')" prop="new_password" required>
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            show-password
            name="new-password"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-button type="primary" :icon="Check" :loading="savingPassword" @click="savePassword">{{ t('settings.passwordSubmit') }}</el-button>
      </el-form>
    </article>

    <article class="settings-card settings-card--mqtt">
      <div class="settings-card__head">
        <span class="settings-card__icon"><el-icon><Connection /></el-icon></span>
        <div>
          <h2>{{ t('settings.mqttTitle') }}</h2>
          <p>{{ t('settings.mqttDescription') }}</p>
        </div>
      </div>

      <div v-if="!mqttServicesEnabled" class="settings-unavailable">
        {{ t('settings.mqttUnavailable') }}
      </div>

      <el-form v-else ref="mqttFormRef" :model="mqttForm" :rules="mqttRules" class="settings-form" label-position="top">
        <div class="form-grid">
          <el-form-item label="Host" prop="host" required>
            <el-input v-model="mqttForm.host" placeholder="broker.example.com" />
          </el-form-item>
          <el-form-item label="Port">
            <el-input-number v-model="mqttForm.port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
        </div>

        <div class="switch-row">
          <div>
            <strong>{{ t('settings.tlsTitle') }}</strong>
            <span>{{ t('settings.tlsDescription') }}</span>
          </div>
          <el-switch v-model="mqttForm.tls" />
        </div>

        <div class="action-row">
          <el-button type="primary" :icon="Check" :loading="savingMqtt" @click="saveMqtt">{{ t('settings.saveMqtt') }}</el-button>
          <el-button :icon="RefreshLeft" :loading="resettingMqtt" @click="resetMqtt">{{ t('settings.resetMqtt') }}</el-button>
          <el-button :icon="Connection" :loading="testingMqtt" @click="testMqtt">{{ t('settings.testConnection') }}</el-button>
        </div>
      </el-form>
    </article>

    <article class="settings-card settings-card--backup">
      <div class="settings-card__head settings-card__head--split">
        <div class="settings-card__title-line">
          <span class="settings-card__icon"><el-icon><Files /></el-icon></span>
          <div>
            <h2>{{ t('settings.backupTitle') }}</h2>
            <p>{{ t('settings.backupDescription') }}</p>
          </div>
        </div>
        <div class="settings-card__head-actions">
          <input ref="snapshotImportInput" class="snapshot-import-input" type="file" accept=".zip,application/zip" @change="handleSnapshotImport" />
          <el-button :icon="Upload" :loading="importingSnapshot" @click="openSnapshotImport">{{ t('settings.importSnapshot') }}</el-button>
          <el-button type="primary" :icon="Plus" :loading="creatingSnapshot" @click="createSnapshot">{{ t('settings.createSnapshot') }}</el-button>
        </div>
      </div>

      <div class="snapshot-list">
        <div v-for="snapshot in snapshots" :key="snapshot.id" class="snapshot-card">
          <div class="snapshot-card__main">
            <span class="snapshot-card__icon"><el-icon><Files /></el-icon></span>
            <div>
              <h3>{{ formatDateTime(snapshot.created_at) }}</h3>
              <p>{{ snapshot.note || t('common.noRemark') }}</p>
            </div>
          </div>
          <div class="snapshot-card__meta">
            <span>{{ snapshot.size }} bytes</span>
            <div class="snapshot-card__actions">
              <el-button size="small" :icon="Edit" @click="editSnapshotNote(snapshot)">{{ t('settings.editSnapshotNote') }}</el-button>
              <el-button size="small" :icon="Download" @click="exportSnapshot(snapshot)">{{ t('settings.exportSnapshot') }}</el-button>
              <el-button size="small" @click="restoreSnapshot(snapshot.id)">{{ t('settings.restore') }}</el-button>
              <el-button size="small" type="danger" plain :icon="Delete" @click="removeSnapshot(snapshot.id)">{{ t('common.delete') }}</el-button>
            </div>
          </div>
        </div>

        <div v-if="!snapshots.length" class="snapshot-empty">
          <span class="settings-card__icon"><el-icon><Files /></el-icon></span>
          <strong>{{ t('settings.noSnapshots') }}</strong>
          <span>{{ t('settings.snapshotEmptyDescription') }}</span>
        </div>
      </div>
    </article>

    <el-dialog
      v-model="restoringSnapshot"
      width="420px"
      align-center
      append-to-body
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :lock-scroll="true"
      class="restore-progress-dialog"
    >
      <div class="restore-progress">
        <span class="restore-progress__icon"><el-icon class="is-loading"><RefreshLeft /></el-icon></span>
        <div>
          <h3>{{ t('settings.snapshotRestoringTitle') }}</h3>
          <p>{{ t('settings.snapshotRestoringDescription') }}</p>
        </div>
      </div>
    </el-dialog>
  </section>
</template>

<style scoped>
.settings-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(15, 139, 141, 0.1), transparent 45%),
    linear-gradient(180deg, var(--app-surface) 0%, var(--app-surface-sunken) 100%);
  box-shadow: var(--app-shadow-md);
}

.settings-hero__eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.page-title {
  margin: 6px 0 0;
  color: var(--app-text);
  font-size: 30px;
}

.page-description {
  margin: 8px 0 0;
  color: var(--app-muted);
  line-height: 1.6;
}

.settings-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.72fr) minmax(360px, 1.28fr);
  gap: 18px;
  margin-top: 20px;
}

.settings-card {
  display: grid;
  gap: 18px;
  padding: 20px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}

.settings-card--backup {
  grid-column: 1 / -1;
}

.settings-card--language {
  align-content: start;
}

.settings-card__head,
.settings-card__title-line {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.settings-card__head--split {
  justify-content: space-between;
}

.settings-card__head-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.settings-card__icon,
.snapshot-card__icon {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--app-border-accent);
  border-radius: 8px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
}

.settings-card h2,
.settings-card h3 {
  margin: 0;
  color: var(--app-text);
}

.settings-card h2 {
  font-size: 19px;
}

.settings-card p {
  margin: 6px 0 0;
  color: var(--app-muted);
  line-height: 1.5;
}

.settings-form {
  display: grid;
  gap: 2px;
}

.settings-form--compact {
  align-content: start;
}

:deep(.theme-mode-segmented.el-segmented) {
  width: 100%;
  min-height: 40px;
  padding: 2px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: none;
}

.theme-mode-segmented :deep(.el-segmented__group) {
  width: 100%;
}

.theme-mode-segmented :deep(.el-segmented__item) {
  flex: 1 1 0;
  min-width: 0;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 6px;
  color: var(--app-muted);
  transition: color 160ms ease, background-color 160ms ease;
}

.theme-mode-segmented :deep(.el-segmented__item-label) {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
}

.theme-mode-segmented :deep(.el-segmented__item.is-selected) {
  color: var(--app-text-strong);
}

.theme-mode-segmented :deep(.el-segmented__item-selected) {
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface-sunken);
  box-shadow: none;
}

:root[data-theme='dark'] :deep(.theme-mode-segmented.el-segmented) {
  border-color: var(--app-border);
  background: var(--app-surface-sunken);
  box-shadow: none;
}

:root[data-theme='dark'] .theme-mode-segmented :deep(.el-segmented__item) {
  color: var(--app-faint);
}

:root[data-theme='dark'] .theme-mode-segmented :deep(.el-segmented__item:hover:not(.is-selected)) {
  background: color-mix(in srgb, var(--app-surface-interactive) 88%, transparent);
  color: var(--app-text);
}

:root[data-theme='dark'] .theme-mode-segmented :deep(.el-segmented__item.is-selected) {
  color: var(--app-text-strong);
}

:root[data-theme='dark'] .theme-mode-segmented :deep(.el-segmented__item-selected) {
  border-color: var(--app-border-strong);
  background: var(--app-surface-elevated);
  box-shadow: none;
}

.credential-autocomplete-anchor {
  position: fixed;
  width: 1px;
  height: 1px;
  padding: 0;
  border: 0;
  opacity: 0;
  pointer-events: none;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}

.switch-row strong,
.switch-row span {
  display: block;
}

.switch-row strong {
  color: var(--app-text);
}

.switch-row span {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 13px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.snapshot-list {
  display: grid;
  gap: 12px;
}

.snapshot-import-input {
  display: none;
}

.snapshot-card {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

.snapshot-card__main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.snapshot-card__main h3 {
  overflow-wrap: anywhere;
  font-size: 16px;
}

.snapshot-card__meta {
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--app-muted);
  font-size: 13px;
}

.snapshot-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.snapshot-empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 170px;
  padding: 22px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 8px;
  color: var(--app-muted);
  text-align: center;
}

.snapshot-empty strong {
  color: var(--app-text);
}

.restore-progress {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 4px 2px;
}

.restore-progress__icon {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--app-border-accent);
  border-radius: 8px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
  font-size: 22px;
}

.restore-progress h3 {
  margin: 0;
  color: var(--app-text-strong);
  font-size: 18px;
}

.restore-progress p {
  margin: 6px 0 0;
  color: var(--app-muted);
  line-height: 1.6;
}

@media (max-width: 980px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .settings-hero,
  .settings-card__head--split,
  .settings-card__head-actions,
  .switch-row,
  .snapshot-card,
  .snapshot-card__meta {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
