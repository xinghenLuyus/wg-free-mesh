import { defineStore } from 'pinia'
import { computed, shallowRef } from 'vue'

import { api } from '@/api/modules'
import { DEFAULT_LOCALE, normalizeLocale, setI18nLocale } from '@/i18n'
import type { AppLocale, AppThemeMode, UiSettingsRead } from '@/types/api'

const LOCALE_STORAGE_KEY = 'wfm_ui_locale'
const THEME_MODE_STORAGE_KEY = 'wfm_ui_theme_mode'
const DARK_MEDIA_QUERY = '(prefers-color-scheme: dark)'

let darkThemeWatcherBound = false

export function normalizeThemeMode(value: string | null | undefined): AppThemeMode {
  if (value === 'light' || value === 'dark') return value
  return 'system'
}

export function readStoredLocale() {
  return normalizeLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY) || navigator.language)
}

export function readStoredThemeMode() {
  return normalizeThemeMode(window.localStorage.getItem(THEME_MODE_STORAGE_KEY))
}

function systemPrefersDark() {
  return window.matchMedia(DARK_MEDIA_QUERY).matches
}

function resolvedTheme(mode: AppThemeMode): 'light' | 'dark' {
  if (mode === 'light' || mode === 'dark') return mode
  return systemPrefersDark() ? 'dark' : 'light'
}

function bindSystemThemeWatcher() {
  if (darkThemeWatcherBound) return
  const media = window.matchMedia(DARK_MEDIA_QUERY)
  const applyCurrent = () => {
    if (readStoredThemeMode() === 'system') {
      applyThemeMode('system')
    }
  }
  if (typeof media.addEventListener === 'function') {
    media.addEventListener('change', applyCurrent)
  } else {
    media.addListener(applyCurrent)
  }
  darkThemeWatcherBound = true
}

export function applyThemeMode(mode: AppThemeMode) {
  const resolved = resolvedTheme(mode)
  window.localStorage.setItem(THEME_MODE_STORAGE_KEY, mode)
  document.documentElement.dataset.themeMode = mode
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
  bindSystemThemeWatcher()
}

export const usePreferencesStore = defineStore('preferences', () => {
  const locale = shallowRef<AppLocale>(readStoredLocale())
  const themeMode = shallowRef<AppThemeMode>(readStoredThemeMode())
  const loading = shallowRef(false)
  const bootstrapped = shallowRef(false)

  const isEnglish = computed(() => locale.value === 'en-US')
  const resolvedThemeMode = computed<'light' | 'dark'>(() => resolvedTheme(themeMode.value))

  function applyLocale(nextLocale: AppLocale) {
    locale.value = nextLocale
    window.localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale)
    setI18nLocale(nextLocale)
  }

  function applyUiTheme(nextThemeMode: AppThemeMode) {
    themeMode.value = nextThemeMode
    applyThemeMode(nextThemeMode)
  }

  function applyUiSettings(settings: UiSettingsRead) {
    applyLocale(normalizeLocale(settings.locale))
    applyUiTheme(normalizeThemeMode(settings.theme_mode))
  }

  async function load(force = false) {
    if (bootstrapped.value && !force) {
      return { locale: locale.value, theme_mode: themeMode.value }
    }
    loading.value = true
    try {
      applyUiSettings(await api.uiSettings())
    } catch {
      applyLocale(readStoredLocale() || DEFAULT_LOCALE)
      applyUiTheme(readStoredThemeMode())
    } finally {
      loading.value = false
      bootstrapped.value = true
    }
    return { locale: locale.value, theme_mode: themeMode.value }
  }

  async function save(payload: Partial<UiSettingsRead>) {
    const previous = { locale: locale.value, theme_mode: themeMode.value }
    if (payload.locale) {
      applyLocale(normalizeLocale(payload.locale))
    }
    if (payload.theme_mode) {
      applyUiTheme(normalizeThemeMode(payload.theme_mode))
    }
    loading.value = true
    try {
      const settings = await api.updateUiSettings({
        locale: payload.locale ?? locale.value,
        theme_mode: payload.theme_mode ?? themeMode.value,
      })
      applyUiSettings(settings)
      return settings
    } catch (error) {
      applyUiSettings(previous)
      throw error
    } finally {
      loading.value = false
    }
  }

  return {
    locale,
    themeMode,
    loading,
    bootstrapped,
    isEnglish,
    resolvedThemeMode,
    applyLocale,
    applyUiTheme,
    applyUiSettings,
    load,
    save,
  }
})
