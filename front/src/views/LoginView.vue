<script setup lang="ts">
import { Key, User } from '@element-plus/icons-vue'
import { reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { notify } from '@/utils/notify'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const form = reactive({
  username: 'admin',
  password: '',
})

async function submit() {
  try {
    await authStore.login(form.username, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '登录失败')
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
          <el-input v-model="form.username" autocomplete="username" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" :prefix-icon="Key" />
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
  background:
    linear-gradient(135deg, rgba(15, 139, 141, 0.12), transparent 42%),
    linear-gradient(315deg, rgba(47, 158, 68, 0.08), transparent 35%),
    var(--app-bg);
}

.login-panel {
  width: min(420px, calc(100vw - 32px));
  padding: 30px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--app-shadow-lg);
  backdrop-filter: blur(10px);
}

.login-title {
  margin: 0;
  font-size: 28px;
  color: var(--app-text);
}

.login-description {
  margin: 8px 0 24px;
  color: var(--app-muted);
}
</style>
