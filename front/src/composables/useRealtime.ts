import { onBeforeUnmount, shallowRef } from 'vue'

import type { RealtimeEvent } from '@/types/api'

export function useRealtime(onMessage: (event: RealtimeEvent) => void) {
  const connected = shallowRef(false)
  const error = shallowRef('')
  const socket = shallowRef<WebSocket | null>(null)

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/events`)
    ws.onopen = () => {
      connected.value = true
      error.value = ''
    }
    ws.onclose = () => {
      connected.value = false
    }
    ws.onerror = () => {
      error.value = '实时连接已断开'
    }
    ws.onmessage = (raw) => {
      const event = JSON.parse(raw.data) as RealtimeEvent
      onMessage(event)
    }
    socket.value = ws
  }

  function disconnect() {
    socket.value?.close()
    socket.value = null
    connected.value = false
  }

  onBeforeUnmount(disconnect)

  return { connected, error, connect, disconnect }
}
