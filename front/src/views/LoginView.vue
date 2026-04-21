<script setup lang="ts">
import { Key, User } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { reactive, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { requiredTextRule } from '@/utils/formRules'
import { notify } from '@/utils/notify'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const authStore = useAuthStore()

const form = reactive({
  username: 'admin',
  password: '',
})
const formRef = shallowRef<FormInstance>()
const formRules: FormRules<typeof form> = {
  username: [requiredTextRule('fields.username')],
  password: [requiredTextRule('fields.password')],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await authStore.login(form.username, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('auth.loginFailed'))
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <h1 class="login-title">{{ t('auth.loginTitle') }}</h1>
      <p class="login-description">{{ t('auth.loginDescription') }}</p>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" @submit.prevent="submit">
        <el-form-item :label="t('fields.username')" prop="username" required>
          <el-input v-model="form.username" autocomplete="username" :prefix-icon="User" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item :label="t('fields.password')" prop="password" required>
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            :prefix-icon="Key"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="authStore.loading" @click="submit">
          {{ t('auth.loginSubmit') }}
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
  background: var(--app-overlay-strong);
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
