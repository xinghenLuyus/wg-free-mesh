import { onBeforeUnmount, shallowRef } from 'vue'

import { translate } from '@/i18n'
import type { RealtimeEvent } from '@/types/api'
import { readAuthToken } from '@/utils/authToken'

type RealtimeState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'degraded'

const STREAM_URL = '/api/v1/events/stream'
const INACTIVITY_TIMEOUT_MS = 45_000
const WATCHDOG_INTERVAL_MS = 5_000
const RECONNECT_BASE_MS = 3_000
const RECONNECT_MAX_MS = 10_000

const connected = shallowRef(false)
const error = shallowRef('')
const state = shallowRef<RealtimeState>('idle')
const lastMessageAt = shallowRef<number | null>(null)
const listeners = new Set<(event: RealtimeEvent) => void>()

const streamController = shallowRef<AbortController | null>(null)
let reconnectTimer: number | null = null
let watchdogTimer: number | null = null
let manualClose = false
let connectPromise: Promise<void> | null = null
let reconnectCount = 0

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

function dispatch(event: RealtimeEvent) {
  for (const listener of listeners) listener(event)
}

function reconnectDelayMs() {
  const next = RECONNECT_BASE_MS * Math.max(1, 2 ** Math.max(0, reconnectCount - 1))
  return Math.min(RECONNECT_MAX_MS, next)
}

function scheduleReconnect() {
  if (manualClose || reconnectTimer !== null || !listeners.size) return
  state.value = 'reconnecting'
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    void ensureStream()
  }, reconnectDelayMs())
}

function closeStream() {
  streamController.value?.abort()
  streamController.value = null
}

function startWatchdog() {
  if (watchdogTimer !== null) return
  watchdogTimer = window.setInterval(() => {
    if (!listeners.size) return
    if (!streamController.value || !connected.value) return
    if (lastMessageAt.value === null) return
    const elapsed = Date.now() - lastMessageAt.value
    if (elapsed <= INACTIVITY_TIMEOUT_MS) return
    state.value = 'degraded'
    connected.value = false
    error.value = translate('realtime.interrupted')
    closeStream()
  }, WATCHDOG_INTERVAL_MS)
}

function parseSseFrame(frame: string): RealtimeEvent | null {
  let eventType = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const separatorIndex = line.indexOf(':')
    const field = separatorIndex >= 0 ? line.slice(0, separatorIndex) : line
    const rawValue = separatorIndex >= 0 ? line.slice(separatorIndex + 1) : ''
    const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue
    if (field === 'event') eventType = value || 'message'
    if (field === 'data') dataLines.push(value)
  }
  if (!dataLines.length) return null

  try {
    const parsed = JSON.parse(dataLines.join('\n')) as Partial<RealtimeEvent>
    return {
      type: typeof parsed.type === 'string' && parsed.type ? parsed.type : eventType,
      timestamp: typeof parsed.timestamp === 'string' ? parsed.timestamp : new Date().toISOString(),
      payload: (parsed.payload ?? parsed) as Record<string, unknown>,
      id: typeof parsed.id === 'string' ? parsed.id : undefined,
    }
  } catch {
    return null
  }
}

async function consumeStream(response: Response) {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error(translate('realtime.unreadable'))
  }
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let boundaryIndex = buffer.indexOf('\n\n')
    while (boundaryIndex >= 0) {
      const frame = buffer.slice(0, boundaryIndex)
      buffer = buffer.slice(boundaryIndex + 2)
      const event = parseSseFrame(frame)
      if (event) {
        lastMessageAt.value = Date.now()
        connected.value = true
        state.value = 'connected'
        dispatch(event)
      }
      boundaryIndex = buffer.indexOf('\n\n')
    }
  }
}

async function openStream() {
  const token = readAuthToken()
  if (!token) {
    connected.value = false
    state.value = 'idle'
    error.value = translate('realtime.missingToken')
    return
  }

  manualClose = false
  const controller = new AbortController()
  streamController.value = controller
  state.value = reconnectCount > 0 ? 'reconnecting' : 'connecting'

  const response = await fetch(STREAM_URL, {
    method: 'GET',
    headers: {
      Accept: 'text/event-stream',
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
    signal: controller.signal,
  })

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(detail || translate('realtime.connectFailed', { status: response.status }))
  }

  if (!response.body) {
    throw new Error(translate('realtime.emptyBody'))
  }

  connected.value = true
  error.value = ''
  state.value = 'connected'
  reconnectCount = 0
  lastMessageAt.value = Date.now()
  clearReconnectTimer()
  startWatchdog()
  await consumeStream(response)
}

async function ensureStream() {
  if (!listeners.size) return
  if (streamController.value || connectPromise) return

  connectPromise = openStream()
    .catch((cause: unknown) => {
      if (manualClose) return
      error.value = cause instanceof Error ? cause.message : translate('realtime.disconnected')
      state.value = 'degraded'
    })
    .finally(() => {
      const wasManualClose = manualClose
      streamController.value = null
      connectPromise = null
      connected.value = false
      if (wasManualClose || !listeners.size) {
        state.value = 'idle'
        return
      }
      reconnectCount += 1
      if (!error.value) error.value = translate('realtime.disconnected')
      scheduleReconnect()
    })

  await connectPromise
}

function releaseStream() {
  if (listeners.size) return
  clearReconnectTimer()
  clearWatchdogTimer()
  manualClose = true
  closeStream()
  connected.value = false
  state.value = 'idle'
}

export function useRealtime(onMessage: (event: RealtimeEvent) => void) {
  function connect() {
    listeners.add(onMessage)
    void ensureStream()
  }

  function disconnect() {
    listeners.delete(onMessage)
    releaseStream()
  }

  onBeforeUnmount(disconnect)

  return {
    connected,
    error,
    state,
    lastMessageAt,
    connect,
    disconnect,
  }
}
