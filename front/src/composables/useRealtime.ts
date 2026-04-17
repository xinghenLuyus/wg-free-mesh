import { onBeforeUnmount, shallowRef } from 'vue'

import type { RealtimeEvent } from '@/types/api'
import { readAuthToken } from '@/utils/authToken'

type RealtimeState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'degraded'

const HEARTBEAT_TIMEOUT_MS = 30_000
const WATCHDOG_INTERVAL_MS = 5_000
const RECONNECT_BASE_MS = 3_000
const RECONNECT_MAX_MS = 10_000

const connected = shallowRef(false)
const error = shallowRef('')
const state = shallowRef<RealtimeState>('idle')
const socket = shallowRef<WebSocket | null>(null)
const lastMessageAt = shallowRef<number | null>(null)
const lastOpenAt = shallowRef<number | null>(null)
const lastCloseAt = shallowRef<number | null>(null)
const lastCloseCode = shallowRef<number | null>(null)
const reconnectAttempts = shallowRef(0)
const listeners = new Set<(event: RealtimeEvent) => void>()
let reconnectTimer: number | null = null
let watchdogTimer: number | null = null
let manualClose = false

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function clearWatchdogTimer() {
  if (watchdogTimer !== null) {
    window.clearInterval(watchdogTimer)
    watchdogTimer = null
  }
}

function startWatchdog() {
  if (watchdogTimer !== null) return
  watchdogTimer = window.setInterval(() => {
    if (!listeners.size) return
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return
    if (lastMessageAt.value === null) return
    const elapsed = Date.now() - lastMessageAt.value
    if (elapsed <= HEARTBEAT_TIMEOUT_MS) return
    state.value = 'degraded'
    connected.value = false
    error.value = '实时连接心跳超时'
    socket.value.close()
  }, WATCHDOG_INTERVAL_MS)
}

function dispatch(event: RealtimeEvent) {
  for (const listener of listeners) listener(event)
}

function reconnectDelayMs() {
  const next = RECONNECT_BASE_MS * Math.max(1, 2 ** Math.max(0, reconnectAttempts.value - 1))
  return Math.min(RECONNECT_MAX_MS, next)
}

function scheduleReconnect() {
  if (manualClose || reconnectTimer !== null || !listeners.size) return
  state.value = 'reconnecting'
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    ensureSocket()
  }, reconnectDelayMs())
}

function bindSocket(ws: WebSocket) {
  ws.onopen = () => {
    connected.value = true
    error.value = ''
    state.value = 'connected'
    reconnectAttempts.value = 0
    lastOpenAt.value = Date.now()
    lastMessageAt.value = Date.now()
    clearReconnectTimer()
  }
  ws.onclose = (event) => {
    if (socket.value === ws) socket.value = null
    connected.value = false
    lastCloseAt.value = Date.now()
    lastCloseCode.value = event.code
    if (!manualClose) {
      error.value = '实时连接已断开'
      reconnectAttempts.value += 1
    } else {
      state.value = 'idle'
    }
    scheduleReconnect()
  }
  ws.onerror = () => {
    error.value = '实时连接发生错误'
  }
  ws.onmessage = (raw) => {
    lastMessageAt.value = Date.now()
    connected.value = true
    state.value = 'connected'
    const event = JSON.parse(raw.data) as RealtimeEvent
    dispatch(event)
  }
}

function ensureSocket() {
  if (!listeners.size) return
  if (socket.value && (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)) return
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = encodeURIComponent(readAuthToken())
  if (!token) {
    connected.value = false
    state.value = 'idle'
    error.value = '缺少实时连接凭证'
    return
  }
  manualClose = false
  state.value = reconnectAttempts.value > 0 ? 'reconnecting' : 'connecting'
  const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/events?token=${token}`)
  socket.value = ws
  bindSocket(ws)
  startWatchdog()
}

function releaseSocket() {
  if (listeners.size) return
  clearReconnectTimer()
  clearWatchdogTimer()
  manualClose = true
  socket.value?.close()
  socket.value = null
  connected.value = false
  state.value = 'idle'
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

  return {
    connected,
    error,
    state,
    lastMessageAt,
    lastOpenAt,
    lastCloseAt,
    lastCloseCode,
    reconnectAttempts,
    connect,
    disconnect,
  }
}
