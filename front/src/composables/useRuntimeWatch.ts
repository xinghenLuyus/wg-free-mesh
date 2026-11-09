import { onMounted, onBeforeUnmount, watch } from 'vue'
import { request } from '@/api/client'

// Visibility is a sampling demand, not an online-status calculation.
type WatchScope = { configId: string; nodeId?: string; mesh?: boolean }
export function useRuntimeWatch(scope: () => WatchScope | WatchScope[]) {
  const viewer = crypto.randomUUID()
  let previous: string[] = []
  let timer: ReturnType<typeof setInterval> | undefined
  function send(active = document.visibilityState === 'visible') {
    const raw = scope()
    const values = Array.isArray(raw) ? raw : [raw]
    const ids = active ? values.map(v => v.configId) : []
    for (const id of previous.filter(id => !ids.includes(id))) {
      void request(`/configs/${id}/runtime-watch`, { method: 'POST', data: { viewer_id: viewer, active: false } }).catch(() => {})
    }
    previous = ids
    if (!active) return
    for (const value of values.filter(v => v.configId)) {
      void request(`/configs/${value.configId}/runtime-watch`, { method: 'POST',
        data: { viewer_id: viewer, node_id: value.nodeId || '', mesh: value.mesh || false } }).catch(() => {})
    }
  }
  function visibility() { send() }
  watch(() => JSON.stringify(scope()), () => send())
  onMounted(() => {
    send()
    timer = setInterval(() => send(), 30000)
    document.addEventListener('visibilitychange', visibility)
  })
  onBeforeUnmount(() => {
    clearInterval(timer)
    document.removeEventListener('visibilitychange', visibility)
    send(false)
  })
}
