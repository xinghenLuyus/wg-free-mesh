<script setup lang="ts">
import { Files, Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigListUpdatedPayload, ConfigRead, RealtimeEvent } from '@/types/api'
import { cidrRule, requiredTextRule } from '@/utils/formRules'
import { notify } from '@/utils/notify'

const router = useRouter()
const { t } = useI18n()

const configs = shallowRef<ConfigRead[]>([])
const realtime = useRealtime((event: RealtimeEvent) => {
  if (event.type === 'config.list.updated') {
    configs.value = (event.payload as unknown as ConfigListUpdatedPayload).configs
  }
})
const dialogVisible = shallowRef(false)
const formRef = shallowRef<FormInstance>()
const form = reactive({
  name: '',
  description: '',
  enabled: true,
  virtual_subnet: '10.66.0.0/24',
  default_listen_port: 51820,
  default_mtu: 1420,
  default_dns: '1.1.1.1',
  auto_sync: true,
})
const formRules: FormRules<typeof form> = {
  name: [requiredTextRule('fields.name')],
  virtual_subnet: [cidrRule('home.virtualSubnetField')],
}

async function load() {
  configs.value = await api.configs()
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    const config = await api.createConfig(form)
    dialogVisible.value = false
    await load()
    await router.push(`/configs/${config.id}`)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('home.createFailed'))
  }
}

async function openConfig(configId: string) {
  await router.push(`/configs/${configId}`)
}

onMounted(async () => {
  try {
    await load()
    realtime.connect()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('home.loadFailed'))
  }
})
</script>

<template>
  <section class="home-hero">
    <div class="home-hero__content">
      <span class="home-hero__eyebrow">{{ t('home.eyebrow') }}</span>
      <h1 class="page-title">{{ t('home.title') }}</h1>
      <p class="page-description">{{ t('home.description') }}</p>
    </div>
    <el-button type="primary" :icon="Plus" @click="dialogVisible = true">{{ t('home.createConfig') }}</el-button>
  </section>

  <section class="config-grid">
    <button
      v-for="config in configs"
      :key="config.id"
      class="config-card"
      @click="openConfig(config.id)"
    >
      <div class="config-card__head">
        <span class="config-card__icon">
          <el-icon><Files /></el-icon>
        </span>
        <el-tag :type="config.enabled ? 'success' : 'info'">{{ config.enabled ? t('home.enabled') : t('home.disabled') }}</el-tag>
      </div>

      <div class="config-card__body">
        <h3>{{ config.name }}</h3>
        <p>{{ config.description || t('home.noDescription') }}</p>
      </div>

      <dl class="config-card__meta">
        <div>
          <dt>{{ t('home.virtualSubnet') }}</dt>
          <dd>{{ config.virtual_subnet }}</dd>
        </div>
        <div>
          <dt>{{ t('home.nodeCount') }}</dt>
          <dd>{{ config.node_count }}</dd>
        </div>
      </dl>
    </button>

    <div v-if="!configs.length" class="config-empty">
      <span class="config-empty__icon">
        <el-icon><Files /></el-icon>
      </span>
      <strong>{{ t('home.emptyTitle') }}</strong>
      <span>{{ t('home.emptyDescription') }}</span>
      <el-button type="primary" :icon="Plus" @click="dialogVisible = true">{{ t('home.createConfig') }}</el-button>
    </div>
  </section>

  <el-dialog v-model="dialogVisible" :title="t('home.dialogTitle')" width="560px">
    <div class="dialog-intro">
      <span class="dialog-intro__icon">
        <el-icon><Files /></el-icon>
      </span>
      <div>
        <h3>{{ t('home.dialogHeading') }}</h3>
        <p>{{ t('home.dialogDescription') }}</p>
      </div>
    </div>

    <el-form ref="formRef" :model="form" :rules="formRules" class="dialog-form" label-position="top">
      <el-form-item :label="t('fields.name')" prop="name" required>
        <el-input v-model="form.name" :placeholder="t('home.exampleName')" />
      </el-form-item>
      <el-form-item :label="t('home.descriptionField')">
        <el-input v-model="form.description" type="textarea" :rows="3" :placeholder="t('home.descriptionPlaceholder')" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item :label="t('home.virtualSubnetField')" prop="virtual_subnet" required>
          <el-input v-model="form.virtual_subnet" />
        </el-form-item>
        <el-form-item :label="t('home.defaultListenPort')">
          <el-input-number v-model="form.default_listen_port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('home.defaultMtu')">
          <el-input-number v-model="form.default_mtu" :min="576" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('home.defaultDns')">
          <el-input v-model="form.default_dns" />
        </el-form-item>
      </div>
      <div class="switch-row">
        <div>
          <strong>{{ t('home.autoSync') }}</strong>
          <span>{{ t('home.autoSyncDescription') }}</span>
        </div>
        <el-switch v-model="form.auto_sync" />
      </div>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :icon="Plus" @click="submit">{{ t('home.create') }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.home-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(15, 139, 141, 0.1), transparent 46%),
    linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-md);
}

.home-hero__content {
  display: grid;
  gap: 8px;
}

.home-hero__eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.page-title {
  margin: 0;
  color: var(--app-text);
  font-size: 30px;
  line-height: 1.2;
}

.page-description {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.6;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(286px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.config-card {
  display: grid;
  gap: 18px;
  min-height: 224px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-sm);
  cursor: pointer;
  text-align: left;
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.config-card:hover {
  transform: translateY(-3px);
  border-color: var(--app-border-accent);
  box-shadow: var(--app-shadow-md);
}

.config-card:focus-visible {
  outline: 0;
  box-shadow: var(--app-focus), var(--app-shadow-md);
}

.config-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.config-card__icon,
.config-empty__icon,
.dialog-intro__icon {
  display: inline-grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--app-border-accent);
  border-radius: 8px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
}

.config-card__body {
  display: grid;
  gap: 8px;
}

.config-card__body h3 {
  margin: 0;
  color: var(--app-text-strong);
  font-size: 20px;
  line-height: 1.25;
}

.config-card__body p {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.6;
}

.config-card__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.config-card__meta div {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}

.config-card__meta dt {
  color: var(--app-faint);
  font-size: 12px;
}

.config-card__meta dd {
  overflow: hidden;
  margin: 6px 0 0;
  color: var(--app-text);
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 224px;
  padding: 24px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 8px;
  background: var(--app-overlay);
  color: var(--app-muted);
  text-align: center;
}

.config-empty strong {
  color: var(--app-text);
}

.dialog-intro {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-sunken);
}

.dialog-intro h3 {
  margin: 0;
  color: var(--app-text);
}

.dialog-intro p {
  margin: 5px 0 0;
  color: var(--app-muted);
  line-height: 1.5;
}

.dialog-form {
  display: grid;
  gap: 2px;
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
  padding: 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: 8px;
  background: var(--app-surface-interactive);
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

@media (max-width: 720px) {
  .home-hero,
  .switch-row {
    flex-direction: column;
    align-items: stretch;
  }

  .form-grid,
  .config-card__meta {
    grid-template-columns: 1fr;
  }
}
</style>
