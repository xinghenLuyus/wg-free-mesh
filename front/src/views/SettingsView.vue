<script setup lang="ts">
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
  <section class="content-card">
    <h1 class="page-title">系统设置</h1>
  </section>

  <section class="content-band section-gap">
    <h2 class="section-title">修改登录密码</h2>
    <el-form label-position="top">
      <el-form-item label="当前密码">
        <el-input v-model="passwordForm.current_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="passwordForm.new_password" type="password" show-password />
      </el-form-item>
      <el-button type="primary" @click="savePassword">修改密码</el-button>
    </el-form>
  </section>

  <section class="content-band section-gap">
    <h2 class="section-title">客户端 MQTT 配置</h2>
    <p class="section-description">这里配置客户端对外可见的 MQTT 公网连接参数。</p>
    <el-form label-position="top">
      <el-form-item label="Host">
        <el-input v-model="mqttForm.host" />
      </el-form-item>
      <el-form-item label="Port">
        <el-input-number v-model="mqttForm.port" :min="1" :max="65535" style="width: 100%" />
      </el-form-item>
      <el-form-item label="Username">
        <el-input v-model="mqttForm.username" />
      </el-form-item>
      <el-form-item label="Password">
        <el-input v-model="mqttForm.password" type="password" show-password />
      </el-form-item>
      <el-switch v-model="mqttForm.tls" active-text="TLS" />
      <div class="mqtt-inline-actions">
        <el-button type="primary" @click="saveMqtt">保存 MQTT</el-button>
        <el-button @click="testMqtt">测试连接</el-button>
        <el-button @click="load">刷新配置</el-button>
      </div>
      <p v-if="mqttTestResult" class="section-description">{{ mqttTestResult }}</p>
    </el-form>
  </section>

  <section class="content-band section-gap">
    <div class="backup-head">
      <h2 class="section-title">备份与恢复</h2>
      <el-button type="primary" @click="createSnapshot">创建快照</el-button>
    </div>
    <el-table :data="snapshots" row-key="id">
      <el-table-column prop="created_at" label="创建时间" min-width="180" />
      <el-table-column prop="note" label="备注" min-width="180" />
      <el-table-column prop="size" label="文件大小" width="120" />
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-space>
            <el-button size="small" @click="restoreSnapshot(row.id)">恢复</el-button>
            <el-button size="small" type="danger" plain @click="removeSnapshot(row.id)">删除</el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.content-card {
  padding: 20px 24px;
  border: 1px solid #d8e1dd;
  border-radius: 8px;
  background: #fff;
}

.page-title,
.section-title {
  margin: 0;
  color: #1f2d28;
}

.section-gap {
  margin-top: 20px;
}

.section-description {
  margin: 8px 0 16px;
  color: #697b74;
  line-height: 1.6;
}

.backup-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.mqtt-inline-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
</style>
