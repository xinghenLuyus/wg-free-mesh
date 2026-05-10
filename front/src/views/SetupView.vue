<script setup lang="ts">
import { Key } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { minLengthTextRule, requiredTextRule } from '@/utils/formRules'
import { notify } from '@/utils/notify'

const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()

const step = shallowRef<'language' | 'password'>('language')
const selectedLocale = shallowRef(preferencesStore.locale)
const form = reactive({
  password: '',
  confirmPassword: '',
})
const formRef = shallowRef<FormInstance>()
const formRules: FormRules<typeof form> = {
  password: [minLengthTextRule('fields.password', 6)],
  confirmPassword: [
    requiredTextRule('fields.confirmPassword'),
    {
      trigger: ['blur', 'change'],
      validator: (_rule, value, callback) => {
        if (String(value || '') !== form.password) {
          callback(new Error(t('validation.passwordMismatch')))
          return
        }
        callback()
      },
    },
  ],
}

function localeLabel(locale: string) {
  return locale === 'en-US' ? t('locale.enUS') : t('locale.zhCN')
}

function nextStep() {
  step.value = 'password'
}

function updateLocale(locale: (typeof SUPPORTED_LOCALES)[number]['code']) {
  selectedLocale.value = locale
  preferencesStore.applyLocale(locale)
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await authStore.setup(form.password, preferencesStore.locale)
    notify.success(t('auth.setupSuccess'))
    await router.push('/')
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('auth.setupFailed'))
  }
}

onMounted(() => {
  preferencesStore.applyLocale(DEFAULT_LOCALE)
  preferencesStore.applyUiTheme('system')
  selectedLocale.value = DEFAULT_LOCALE
})
</script>

<template>
  <div class="setup-page">
    <div class="setup-panel">
      <template v-if="step === 'language'">
        <div class="auth-brand">
          <img class="auth-logo" src="/logo.png" alt="WG Free Mesh" />
          <div>
            <h1 class="setup-title">{{ t('auth.setupLanguageTitle') }}</h1>
            <p class="setup-description">{{ t('auth.setupLanguageDescription') }}</p>
          </div>
        </div>
        <el-form class="setup-form" label-position="top">
          <el-form-item :label="t('locale.label')" required>
            <el-select v-model="selectedLocale" style="width: 100%" @change="updateLocale">
              <el-option
                v-for="locale in SUPPORTED_LOCALES"
                :key="locale.code"
                :label="localeLabel(locale.code)"
                :value="locale.code"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <el-button type="primary" style="width: 100%; margin-top: 18px" @click="nextStep">
          {{ t('auth.setupNext') }}
        </el-button>
      </template>

      <template v-else>
        <div class="auth-brand">
          <img class="auth-logo" src="/logo.png" alt="WG Free Mesh" />
          <div>
            <h1 class="setup-title">{{ t('auth.setupPasswordTitle') }}</h1>
            <p class="setup-description">{{ t('auth.setupPasswordDescription') }}</p>
          </div>
        </div>
        <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" autocomplete="off" @submit.prevent="submit">
          <input
            class="credential-autocomplete-anchor"
            type="text"
            name="username"
            autocomplete="username"
            value="admin"
            readonly
            tabindex="-1"
            aria-hidden="true"
          />
          <el-form-item :label="t('fields.newPassword')" prop="password" required>
            <el-input
              v-model="form.password"
              type="password"
              show-password
              name="new-password"
              autocomplete="new-password"
              :prefix-icon="Key"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-form-item :label="t('fields.confirmPassword')" prop="confirmPassword" required>
            <el-input
              v-model="form.confirmPassword"
              type="password"
              show-password
              name="new-password-confirm"
              autocomplete="new-password"
              :prefix-icon="Key"
              @keyup.enter="submit"
            />
          </el-form-item>
          <div class="setup-actions">
            <el-button @click="step = 'language'">{{ t('auth.setupBack') }}</el-button>
            <el-button type="primary" :loading="authStore.loading" @click="submit">
              {{ t('auth.setupSubmit') }}
            </el-button>
          </div>
        </el-form>
      </template>
    </div>
  </div>
</template>

<style scoped>
.setup-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at 26% 18%, color-mix(in srgb, var(--app-primary) 18%, transparent), transparent 30%),
    radial-gradient(circle at 76% 78%, color-mix(in srgb, var(--el-color-success) 14%, transparent), transparent 34%),
    var(--app-bg);
}

.setup-panel {
  position: relative;
  width: min(520px, calc(100vw - 32px));
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

.setup-panel::before {
  content: "";
  position: absolute;
  inset: 14px;
  pointer-events: none;
  border: 1px solid color-mix(in srgb, var(--app-border-soft) 76%, transparent);
  border-radius: 8px;
}

.setup-panel > * {
  position: relative;
  z-index: 1;
}

.setup-title {
  margin: 0;
  font-size: 32px;
  color: var(--app-text-strong);
  line-height: 1.12;
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

.setup-description {
  margin: 10px 0 0;
  color: var(--app-muted);
  line-height: 1.55;
}

.setup-form {
  display: grid;
  gap: 2px;
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

.setup-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

@media (max-width: 560px) {
  .auth-brand {
    gap: 14px;
  }

  .auth-logo {
    width: 58px;
    height: 58px;
  }

  .setup-title {
    font-size: 26px;
  }
}
</style>
