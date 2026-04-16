import { onBeforeUnmount, shallowRef } from 'vue'

import type { RealtimeEvent } from '@/types/api'
import { readAuthToken } from '@/utils/authToken'

const connected = shallowRef(false)
const error = shallowRef('')
const socket = shallowRef<WebSocket | null>(null)
const listeners = new Set<(event: RealtimeEvent) => void>()
let reconnectTimer: number | null = null
let manualClose = false

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function dispatch(event: RealtimeEvent) {
  for (const listener of listeners) listener(event)
}

function scheduleReconnect() {
  if (manualClose || reconnectTimer !== null || !listeners.size) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    ensureSocket()
  }, 2000)
}

function bindSocket(ws: WebSocket) {
  ws.onopen = () => {
    connected.value = true
    error.value = ''
    clearReconnectTimer()
  }
  ws.onclose = () => {
    if (socket.value === ws) socket.value = null
    connected.value = false
    if (!manualClose) error.value = '实时连接已断开'
    scheduleReconnect()
  }
  ws.onerror = () => {
    error.value = '实时连接已断开'
  }
  ws.onmessage = (raw) => {
    const event = JSON.parse(raw.data) as RealtimeEvent
    dispatch(event)
  }
}

function ensureSocket() {
  if (!listeners.size) return
  if (socket.value && (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)) return
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = encodeURIComponent(readAuthToken())
  manualClose = false
  const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/events?token=${token}`)
  socket.value = ws
  bindSocket(ws)
}

function releaseSocket() {
  if (listeners.size) return
  clearReconnectTimer()
  manualClose = true
  socket.value?.close()
  socket.value = null
  connected.value = false
}

export function useRealtime(onMessage: (event: RealtimeEvent) => void) {
  function connect() {
    listeners.add(onMessage)
    ensureSocket()
  }

  function disconnect() {
    listeners.delete(onMessage)
    releaseSocket()
  }

  onBeforeUnmount(disconnect)

  return { connected, error, connect, disconnect }
}
