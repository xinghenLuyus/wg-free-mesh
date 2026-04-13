<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive } from 'vue'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: 'admin',
  password: '',
})

async function submit() {
  try {
    await authStore.login(form.username, form.password)
    await router.push('/')
  } catch (error) {
    ElMessage.error(error instanceof ApiClientError ? error.message : '登录失败')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <h1 class="login-title">WG Free Mesh</h1>
      <p class="login-description">请输入登录信息</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="authStore.loading" @click="submit">
          登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
  background: #f4f7f5;
}

.login-panel {
  width: min(420px, calc(100vw - 32px));
  padding: 28px;
  border: 1px solid #d9e4dd;
  border-radius: 8px;
  background: #fff;
}

.login-title {
  margin: 0;
  font-size: 28px;
  color: #1f2d28;
}

.login-description {
  margin: 8px 0 24px;
  color: #64756f;
}
</style>
