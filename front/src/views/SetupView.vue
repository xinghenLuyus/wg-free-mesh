<script setup lang="ts">
import { Key } from '@element-plus/icons-vue'
import { computed, reactive } from 'vue'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { notify } from '@/utils/notify'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  password: '',
  confirmPassword: '',
})

const canSubmit = computed(() => form.password.length >= 6 && form.password === form.confirmPassword)

async function submit() {
  if (!canSubmit.value) {
    notify.warning('请填写至少 6 位密码，并确认两次输入一致')
    return
  }
  try {
    await authStore.setup(form.password)
    notify.success('管理员密码已设置')
    await router.push('/')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : '初始化失败')
  }
}
</script>

<template>
  <div class="setup-page">
    <div class="setup-panel">
      <h1 class="setup-title">设置管理员密码</h1>
      <p class="setup-description">首次使用前，请为 admin 设置初始密码。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="新密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="new-password"
            :prefix-icon="Key"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            autocomplete="new-password"
            :prefix-icon="Key"
          />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="authStore.loading" @click="submit">
          完成初始化
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.setup-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
  background:
    linear-gradient(135deg, rgba(15, 139, 141, 0.12), transparent 42%),
    linear-gradient(315deg, rgba(47, 158, 68, 0.08), transparent 35%),
    var(--app-bg);
}

.setup-panel {
  width: min(440px, calc(100vw - 32px));
  padding: 30px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--app-shadow-lg);
  backdrop-filter: blur(10px);
}

.setup-title {
  margin: 0;
  font-size: 28px;
  color: var(--app-text);
}

.setup-description {
  margin: 8px 0 24px;
  color: var(--app-muted);
}
</style>
