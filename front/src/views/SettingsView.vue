<script setup lang="ts">
import { Check, Connection, Delete, Files, Lock, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, shallowRef } from 'vue'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import type { SnapshotRead } from '@/types/api'

const mqttForm = reactive({
  host: '',
  port: 8883,
  tls: true,
  username: '',
  password: '',
})

const passwordForm = reactive({
  current_password: '',
  new_password: '',
})

const snapshots = shallowRef<SnapshotRead[]>([])
const mqttTestResult = shallowRef('')

async function load() {
  Object.assign(mqttForm, await api.mqttSettings())
  snapshots.value = await api.snapshots()
}

async function saveMqtt() {
  try {
    Object.assign(mqttForm, await api.updateMqttSettings({ ...mqttForm }))
    ElMessage.success('MQTT 配置已保存')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : 'MQTT 配置保存失败')
  }
}

async function testMqtt() {
  try {
    const result = await api.testMqttSettings({ ...mqttForm })
    mqttTestResult.value = `${result.success ? '连接成功' : '连接失败'} / ${result.message}`
    ElMessage.success('MQTT 测试已完成')
  } catch (error) {
    mqttTestResult.value = '测试失败'
    ElMessage.error(error instanceof ApiClientError ? error.message : 'MQTT 测试失败')
  }
}

async function savePassword() {
  try {
    await api.changePassword(passwordForm.current_password, passwordForm.new_password)
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    ElMessage.success('密码已更新')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '密码更新失败')
  }
}

async function createSnapshot() {
  try {
    await api.createSnapshot('')
    await load()
    ElMessage.success('快照已创建')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '快照创建失败')
  }
}

async function restoreSnapshot(snapshotId: string) {
  try {
    await api.restoreSnapshot(snapshotId)
    ElMessage.success('快照已恢复')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '快照恢复失败')
  }
}

async function removeSnapshot(snapshotId: string) {
  try {
    await api.deleteSnapshot(snapshotId)
    await load()
    ElMessage.success('快照已删除')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '快照删除失败')
  }
}

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '设置加载失败')
  }
})
</script>

<template>
  <section class="settings-hero">
    <div>
      <span class="settings-hero__eyebrow">System Settings</span>
      <h1 class="page-title">系统设置</h1>
      <p class="page-description">管理登录密码、客户端 MQTT 连接参数和系统快照。</p>
    </div>
    <el-button :icon="Refresh" @click="load">刷新设置</el-button>
  </section>

  <section class="settings-grid">
    <article class="settings-card settings-card--password">
      <div class="settings-card__head">
        <span class="settings-card__icon"><el-icon><Lock /></el-icon></span>
        <div>
          <h2>登录密码</h2>
          <p>更新控制台入口密码。</p>
        </div>
      </div>

      <el-form class="settings-form" label-position="top">
        <el-form-item label="当前密码">
          <el-input v-model="passwordForm.current_password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-button type="primary" :icon="Check" @click="savePassword">修改密码</el-button>
      </el-form>
    </article>

    <article class="settings-card settings-card--mqtt">
      <div class="settings-card__head">
        <span class="settings-card__icon"><el-icon><Connection /></el-icon></span>
        <div>
          <h2>客户端 MQTT 配置</h2>
          <p>配置客户端对外可见的 MQTT 公网连接参数。</p>
        </div>
      </div>

      <el-form class="settings-form" label-position="top">
        <div class="form-grid">
          <el-form-item label="Host">
            <el-input v-model="mqttForm.host" placeholder="broker.example.com" />
          </el-form-item>
          <el-form-item label="Port">
            <el-input-number v-model="mqttForm.port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item label="Username">
            <el-input v-model="mqttForm.username" autocomplete="username" />
          </el-form-item>
          <el-form-item label="Password">
            <el-input v-model="mqttForm.password" type="password" show-password autocomplete="current-password" />
          </el-form-item>
        </div>

        <div class="switch-row">
          <div>
            <strong>TLS 加密</strong>
            <span>客户端连接 MQTT 时是否启用 TLS。</span>
          </div>
          <el-switch v-model="mqttForm.tls" />
        </div>

        <div class="action-row">
          <el-button type="primary" :icon="Check" @click="saveMqtt">保存 MQTT</el-button>
          <el-button :icon="Connection" @click="testMqtt">测试连接</el-button>
          <el-button :icon="Refresh" @click="load">刷新配置</el-button>
        </div>

        <div v-if="mqttTestResult" class="result-callout">
          {{ mqttTestResult }}
        </div>
      </el-form>
    </article>

    <article class="settings-card settings-card--backup">
      <div class="settings-card__head settings-card__head--split">
        <div class="settings-card__title-line">
          <span class="settings-card__icon"><el-icon><Files /></el-icon></span>
          <div>
            <h2>备份与恢复</h2>
            <p>创建快照，并在需要时恢复历史状态。</p>
          </div>
        </div>
        <el-button type="primary" :icon="Plus" @click="createSnapshot">创建快照</el-button>
      </div>

      <div class="snapshot-list">
        <div v-for="snapshot in snapshots" :key="snapshot.id" class="snapshot-card">
          <div class="snapshot-card__main">
            <span class="snapshot-card__icon"><el-icon><Files /></el-icon></span>
            <div>
              <h3>{{ snapshot.created_at }}</h3>
              <p>{{ snapshot.note || '无备注' }}</p>
            </div>
          </div>
          <div class="snapshot-card__meta">
            <span>{{ snapshot.size }} bytes</span>
            <div class="snapshot-card__actions">
              <el-button size="small" @click="restoreSnapshot(snapshot.id)">恢复</el-button>
              <el-button size="small" type="danger" plain :icon="Delete" @click="removeSnapshot(snapshot.id)">删除</el-button>
            </div>
          </div>
        </div>

        <div v-if="!snapshots.length" class="snapshot-empty">
          <span class="settings-card__icon"><el-icon><Files /></el-icon></span>
          <strong>暂无快照</strong>
          <span>创建快照后，这里会显示可恢复的历史状态。</span>
        </div>
      </div>
    </article>
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
    linear-gradient(180deg, #ffffff 0%, #f8fbf9 100%);
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
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfb 100%);
  box-shadow: var(--app-shadow-sm);
}

.settings-card--backup {
  grid-column: 1 / -1;
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

.settings-card__icon,
.snapshot-card__icon {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid #bfe0da;
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
  background: #f8fbf9;
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
  margin-top: 4px;
}

.result-callout {
  padding: 12px 14px;
  border: 1px solid #cfe3dc;
  border-radius: 8px;
  background: #f1f8f6;
  color: #285b52;
  font-weight: 650;
}

.snapshot-list {
  display: grid;
  gap: 12px;
}

.snapshot-card {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 14px;
  border: 1px solid #e0e8e4;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(42, 65, 58, 0.045);
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

@media (max-width: 980px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .settings-hero,
  .settings-card__head--split,
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
