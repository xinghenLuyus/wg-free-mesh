import { createI18n } from 'vue-i18n'

import enUS from '@/i18n/messages/en-US'
import zhCN from '@/i18n/messages/zh-CN'
import type { AppLocale } from '@/types/api'

export interface LocaleOption {
  code: AppLocale
  labelKey: string
}

export const SUPPORTED_LOCALES: LocaleOption[] = [
  { code: 'zh-CN', labelKey: 'locale.zhCN' },
  { code: 'en-US', labelKey: 'locale.enUS' },
]
export const DEFAULT_LOCALE: AppLocale = 'zh-CN'

export function normalizeLocale(value: string | null | undefined): AppLocale {
  if (value === 'en-US') return 'en-US'
  if (value === 'zh-CN') return 'zh-CN'
  if (value?.toLowerCase().startsWith('en')) return 'en-US'
  return DEFAULT_LOCALE
}

export const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setI18nLocale(locale: AppLocale) {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
}

export function translate(key: string, named?: Record<string, unknown>) {
  return i18n.global.t(key, named ?? {})
}

export function hasTranslation(key: string) {
  return i18n.global.te(key)
}
