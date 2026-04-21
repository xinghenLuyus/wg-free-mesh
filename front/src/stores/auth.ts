import { defineStore } from 'pinia'
import { computed, shallowRef } from 'vue'

import { api } from '@/api/modules'
import type { AppLocale, AuthStateRead, TokenSessionRead } from '@/types/api'
import { clearAuthToken, readAuthToken, writeAuthToken } from '@/utils/authToken'

export const useAuthStore = defineStore('auth', () => {
  const token = shallowRef(readAuthToken())
  const state = shallowRef<AuthStateRead | null>(null)
  const loading = shallowRef(false)
  const bootstrapped = shallowRef(false)

  const setupRequired = computed(() => state.value?.setup_required === true)
  const authenticated = computed(() => state.value?.authenticated === true && Boolean(token.value))
  const displayName = computed(() => state.value?.display_name || '')

  function applyTokenSession(session: TokenSessionRead) {
    token.value = session.access_token
    writeAuthToken(session.access_token)
    state.value = {
      setup_required: session.setup_required,
      authenticated: session.authenticated,
      username: session.username,
      display_name: session.display_name,
      expires_at: session.expires_at,
    }
    bootstrapped.value = true
  }

  function clearAuth() {
    token.value = ''
    clearAuthToken()
    if (state.value) {
      state.value = { ...state.value, authenticated: false, username: '', display_name: '', expires_at: null }
    }
  }

  async function setup(password: string, locale: AppLocale) {
    loading.value = true
    try {
      applyTokenSession(await api.setup(password, locale))
    } finally {
      loading.value = false
    }
  }

  async function login(username: string, password: string) {
    loading.value = true
    try {
      applyTokenSession(await api.login(username, password))
    } finally {
      loading.value = false
    }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    loading.value = true
    try {
      applyTokenSession(await api.changePassword(currentPassword, newPassword))
    } finally {
      loading.value = false
    }
  }

  async function loadState(force = false) {
    if (bootstrapped.value && !force) return state.value
    state.value = await api.authState()
    bootstrapped.value = true
    if (!state.value.authenticated) {
      token.value = ''
      clearAuthToken()
    }
    return state.value
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      clearAuth()
      bootstrapped.value = false
    }
  }

  return {
    token,
    state,
    loading,
    bootstrapped,
    setupRequired,
    authenticated,
    displayName,
    setup,
    login,
    changePassword,
    loadState,
    logout,
    clearAuth,
  }
})
