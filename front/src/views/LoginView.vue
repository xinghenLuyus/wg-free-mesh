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
      <div class="auth-brand">
        <img class="auth-logo" src="/logo.png" alt="WG Free Mesh" />
        <div>
          <h1 class="login-title">{{ t('auth.loginTitle') }}</h1>
          <p class="login-description">{{ t('auth.loginDescription') }}</p>
        </div>
      </div>
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
  padding: 24px;
  background:
    radial-gradient(circle at 26% 18%, color-mix(in srgb, var(--app-primary) 18%, transparent), transparent 30%),
    radial-gradient(circle at 76% 78%, color-mix(in srgb, var(--el-color-success) 14%, transparent), transparent 34%),
    var(--app-bg);
}

.login-panel {
  position: relative;
  width: min(500px, calc(100vw - 32px));
  padding: 34px;
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--app-primary) 10%, transparent), transparent 52%),
    var(--app-overlay-strong);
  box-shadow: var(--app-shadow-lg);
  backdrop-filter: blur(10px);
}

.login-panel::before {
  content: "";
  position: absolute;
  inset: 14px;
  pointer-events: none;
  border: 1px solid color-mix(in srgb, var(--app-border-soft) 76%, transparent);
  border-radius: 8px;
}

.login-panel > * {
  position: relative;
  z-index: 1;
}

.login-title {
  margin: 0;
  font-size: 34px;
  color: var(--app-text-strong);
  line-height: 1.08;
}

.auth-brand {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  min-width: 0;
  margin-bottom: 26px;
}

.auth-brand > div {
  min-width: 0;
}

.auth-logo {
  width: 78px;
  height: 78px;
  flex: 0 0 auto;
  border-radius: 8px;
  object-fit: contain;
  filter: drop-shadow(0 14px 22px color-mix(in srgb, var(--app-primary) 24%, transparent));
}

.login-description {
  margin: 10px 0 0;
  color: var(--app-muted);
  line-height: 1.55;
}

@media (max-width: 560px) {
  .auth-brand {
    gap: 14px;
  }

  .auth-logo {
    width: 58px;
    height: 58px;
  }

  .login-title {
    font-size: 28px;
  }
}
</style>
