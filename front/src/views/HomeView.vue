<script setup lang="ts">
import { Files, Plus } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import type { ConfigListUpdatedPayload, ConfigRead, RealtimeEvent } from '@/types/api'
import { requiredTextRule } from '@/utils/formRules'
import { notify } from '@/utils/notify'

const router = useRouter()

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
  name: [requiredTextRule('名称')],
  virtual_subnet: [requiredTextRule('虚拟子网')],
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
    notify.error(error instanceof ApiClientError ? error.message : '配置创建失败')
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
    notify.error(error instanceof ApiClientError ? error.message : '配置加载失败')
  }
})
</script>

<template>
  <section class="home-hero">
    <div class="home-hero__content">
      <span class="home-hero__eyebrow">WireGuard Control Plane</span>
      <h1 class="page-title">WireGuard 配置管理</h1>
      <p class="page-description">以配置为入口管理 Mesh 网络、节点和同步态配置。</p>
    </div>
    <el-button type="primary" :icon="Plus" @click="dialogVisible = true">创建配置</el-button>
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
        <el-tag :type="config.enabled ? 'success' : 'info'">{{ config.enabled ? '启用' : '停用' }}</el-tag>
      </div>

      <div class="config-card__body">
        <h3>{{ config.name }}</h3>
        <p>{{ config.description || '未填写备注' }}</p>
      </div>

      <dl class="config-card__meta">
        <div>
          <dt>虚拟网段</dt>
          <dd>{{ config.virtual_subnet }}</dd>
        </div>
        <div>
          <dt>节点数</dt>
          <dd>{{ config.node_count }}</dd>
        </div>
      </dl>
    </button>

    <div v-if="!configs.length" class="config-empty">
      <span class="config-empty__icon">
        <el-icon><Files /></el-icon>
      </span>
      <strong>还没有配置</strong>
      <span>先创建第一份配置，再继续维护节点和同步态。</span>
      <el-button type="primary" :icon="Plus" @click="dialogVisible = true">创建配置</el-button>
    </div>
  </section>

  <el-dialog v-model="dialogVisible" title="创建配置" width="560px">
    <div class="dialog-intro">
      <span class="dialog-intro__icon">
        <el-icon><Files /></el-icon>
      </span>
      <div>
        <h3>新建配置</h3>
        <p>配置会作为节点、Mesh 关系和配置同步的统一工作区。</p>
      </div>
    </div>

    <el-form ref="formRef" :model="form" :rules="formRules" class="dialog-form" label-position="top">
      <el-form-item label="名称" prop="name" required>
        <el-input v-model="form.name" placeholder="例如：家庭 Mesh" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选，写清楚这份配置的用途" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="虚拟子网" prop="virtual_subnet" required>
          <el-input v-model="form.virtual_subnet" />
        </el-form-item>
        <el-form-item label="默认监听端口">
          <el-input-number v-model="form.default_listen_port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认 MTU">
          <el-input-number v-model="form.default_mtu" :min="576" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认 DNS">
          <el-input v-model="form.default_dns" />
        </el-form-item>
      </div>
      <div class="switch-row">
        <div>
          <strong>自动同步</strong>
          <span>系统态生成后自动同步到同步态。</span>
        </div>
        <el-switch v-model="form.auto_sync" />
      </div>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :icon="Plus" @click="submit">创建</el-button>
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
    linear-gradient(180deg, #ffffff 0%, #f8fbf9 100%);
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
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfb 100%);
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
  border-color: #9bc8bf;
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
  border: 1px solid #bfe0da;
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
  color: #213029;
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
  border: 1px solid #e1ebe7;
  border-radius: 8px;
  background: #f7fbf9;
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
  background: rgba(255, 255, 255, 0.72);
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
  border: 1px solid #e1ebe7;
  border-radius: 8px;
  background: #f8fbf9;
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
  border: 1px solid #e1ebe7;
  border-radius: 8px;
  background: #fbfcfb;
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
