import { defineStore } from 'pinia'
import { computed, shallowRef } from 'vue'

import { api } from '@/api/modules'
import type { SessionRead } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const session = shallowRef<SessionRead | null>(null)
  const loading = shallowRef(false)

  const authenticated = computed(() => session.value?.authenticated === true)
  const displayName = computed(() => session.value?.display_name || '未登录')

  async function login(username: string, password: string) {
    loading.value = true
    try {
      session.value = await api.login(username, password)
    } finally {
      loading.value = false
    }
  }

  async function loadSession() {
    session.value = await api.session()
  }

  async function logout() {
    session.value = await api.logout()
  }

  return { session, loading, authenticated, displayName, login, loadSession, logout }
})
