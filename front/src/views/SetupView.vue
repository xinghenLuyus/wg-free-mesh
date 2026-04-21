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
        <h1 class="setup-title">{{ t('auth.setupLanguageTitle') }}</h1>
        <p class="setup-description">{{ t('auth.setupLanguageDescription') }}</p>
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
        <h1 class="setup-title">{{ t('auth.setupPasswordTitle') }}</h1>
        <p class="setup-description">{{ t('auth.setupPasswordDescription') }}</p>
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
  background: var(--app-overlay-strong);
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
</style>
