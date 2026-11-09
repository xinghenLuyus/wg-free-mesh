<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Aim, Close, Connection, Files, Monitor, Search, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { request } from '@/api/client'
import { api } from '@/api/modules'
import { useRealtime } from '@/composables/useRealtime'
import { useRuntimeWatch } from '@/composables/useRuntimeWatch'
import { usePreferencesStore, normalizeThemeMode } from '@/stores/preferences'
import { readAuthToken } from '@/utils/authToken'
import { translateMeshText } from '@/utils/meshText'
import { formatDateTime, setSystemTimeZone } from '@/utils/dateTime'
import { useAuthStore } from '@/stores/auth'
import type { TopologyBoard, TopologyConnection } from '@/types/topology'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const preferences = usePreferencesStore()
const auth = useAuthStore()
const configId = String(route.params.configId)
useRuntimeWatch(() => ({ configId, mesh: true }))
const board = ref<TopologyBoard | null>(null)
const error = ref('')
const busy = ref(false)
const selectedNode = ref('')
const selectedEdge = ref('')
const hoverEdge = ref('')
const query = ref('')
const svg = ref<SVGSVGElement>()
const searchInput = ref<HTMLInputElement>()
const searchShortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K'
type Point = { x: number; y: number }
const positions = ref<Record<string, Point>>({})
const colors = ref<Record<string, string>>({})
const camera = ref({ x: 600, y: 400, zoom: 1 })
const dimensions = ref({ width: window.innerWidth, height: window.innerHeight })
const storageKey = 'wfm_topology_' + configId
let timer: ReturnType<typeof setTimeout> | undefined
let periodic: ReturnType<typeof setInterval> | undefined
let disposed = false
let drag: { id: string; x: number; y: number; start: Point; moved: boolean; pointer: number } | null = null
let suppressClick = false

try {
  const saved = JSON.parse(localStorage.getItem(storageKey) || '{}')
  for (const [id, point] of Object.entries(saved.layoutVersion === 2 ? saved.positions || {} : {})) {
    const p = point as Point
    if (Number.isFinite(p.x) && Number.isFinite(p.y)) positions.value[id] = p
  }
  for (const [id, color] of Object.entries(saved.colors || {})) {
    if (typeof color === 'string' && /^#[0-9a-f]{6}$/i.test(color)) colors.value[id] = color
  }
} catch { /* An invalid or unavailable browser cache is not a graph error. */ }

const nodes = computed(() => board.value?.nodes || [])
const connections = computed(() => board.value?.connections || [])
const hasValidationErrors = computed(() => !!board.value?.issues.length || connections.value.some(e => e.validation_errors.length > 0))
const hasDisabledElements = computed(() => nodes.value.some(n => !n.enabled) || connections.value.some(e => !e.enabled))
const connectionLanes = computed(() => {
  const groups = new Map<string, TopologyConnection[]>()
  for (const connection of connections.value) {
    const key = JSON.stringify([connection.source, connection.target].sort())
    const group = groups.get(key) || []
    group.push(connection); groups.set(key, group)
  }
  const lanes = new Map<string, { index: number; count: number; offset: number }>()
  for (const group of groups.values()) {
    group.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
    group.forEach((connection, index) => lanes.set(connection.id, {
      index: index + 1, count: group.length, offset: (index - (group.length - 1) / 2) * 112,
    }))
  }
  return lanes
})
const degrees = computed(() => {
  const values: Record<string, number> = {}
  for (const e of connections.value) { values[e.source] = (values[e.source] || 0) + 1; values[e.target] = (values[e.target] || 0) + 1 }
  return values
})
const nodeMap = computed(() => new Map(nodes.value.map(n => [n.id, n])))
const node = computed(() => nodeMap.value.get(selectedNode.value))
const edge = computed(() => connections.value.find(e => e.id === selectedEdge.value))
const adjacent = computed(() => new Set(connections.value.filter(e => e.source === selectedNode.value || e.target === selectedNode.value).flatMap(e => [e.source, e.target])))
const related = computed(() => connections.value.filter(e => e.source === selectedNode.value || e.target === selectedNode.value))
const results = computed(() => query.value.trim() ? nodes.value.filter(n => (n.name + ' ' + n.virtual_ip).toLowerCase().includes(query.value.toLowerCase())).slice(0, 8) : [])
const expanded = computed(() => selectedEdge.value || hoverEdge.value)
const reasonKey: Record<string, string> = { handshake: 'handshakeReason', disabled_or_invalid: 'disabled', both_offline: 'bothOffline', interface_stopped: 'stopped', missing_handshake_or_peer: 'missing', no_observation: 'none', static: 'static' }

function save() {
  try { localStorage.setItem(storageKey, JSON.stringify({ layoutVersion: 2, positions: positions.value, colors: colors.value })) } catch { /* Private browsing may disallow persistence. */ }
}
function point(id: string): Point {
  return positions.value[id] || { x: 0, y: 0 }
}
function fit() {
  const pts = nodes.value.map(n => positions.value[n.id]).filter((p): p is Point => !!p)
  if (!pts.length) return
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y)
  const x0 = Math.min(...xs) - 100, x1 = Math.max(...xs) + 100
  const y0 = Math.min(...ys) - 95, y1 = Math.max(...ys) + 135
  const sidePadding = dimensions.value.width < 600 ? 50 : 340
  const zoom = Math.min(1.5, (dimensions.value.width - sidePadding) / (x1 - x0), (dimensions.value.height - 230) / (y1 - y0))
  camera.value = { x: dimensions.value.width / 2 - (x0 + x1) / 2 * zoom, y: dimensions.value.height / 2 - (y0 + y1) / 2 * zoom, zoom: Math.max(.08, zoom) }
}
function layout() {
  const list = nodes.value
  const radius = Math.max(200, Math.sqrt(list.length) * 85)
  const next: Record<string, Point> = {}
  list.forEach((n, i) => { const angle = 2 * Math.PI * i / Math.max(1, list.length) - Math.PI / 2; next[n.id] = { x: radius * Math.cos(angle), y: radius * Math.sin(angle) } })
  const hub = [...list].sort((a, b) => (degrees.value[b.id] || 0) - (degrees.value[a.id] || 0))[0]
  if (hub && (degrees.value[hub.id] || 0) >= 3 && list.length < 20 && (degrees.value[hub.id] || 0) > connections.value.length * 2 / list.length * 1.3) {
    next[hub.id] = { x: 0, y: 0 }
    const leaves = list.filter(n => n.id !== hub.id)
    leaves.forEach((n, i) => { const angle = 2 * Math.PI * i / leaves.length - Math.PI / 2; next[n.id] = { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius } })
  }
  if (list.length === 1) next[list[0]!.id] = { x: 0, y: 0 }
  if (list.length >= 120) {
    const columns = Math.ceil(Math.sqrt(list.length))
    list.forEach((n, i) => { next[n.id] = { x: (i % columns) * 170, y: Math.floor(i / columns) * 170 } })
  }
  // Bounded deterministic relaxation; runtime updates never rerun the layout.
  if (list.length < 120) for (let iteration = 0; iteration < 100; iteration++) {
    const shifts = Object.fromEntries(list.map(n => [n.id, { x: 0, y: 0 }]))
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const a = list[i]!, b = list[j]!, pa = next[a.id]!, pb = next[b.id]!
      const dx = pa.x - pb.x, dy = pa.y - pb.y, distance = Math.max(1, Math.hypot(dx, dy))
      const force = Math.min(10, 14000 / distance ** 2)
      shifts[a.id]!.x += dx / distance * force; shifts[a.id]!.y += dy / distance * force
      shifts[b.id]!.x -= dx / distance * force; shifts[b.id]!.y -= dy / distance * force
    }
    for (const e of connections.value) {
      const a = next[e.source], b = next[e.target]
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y, distance = Math.max(1, Math.hypot(dx, dy))
      const force = (distance - 280) * .015
      shifts[e.source]!.x += dx / distance * force; shifts[e.source]!.y += dy / distance * force
      shifts[e.target]!.x -= dx / distance * force; shifts[e.target]!.y -= dy / distance * force
    }
    for (const n of list) { next[n.id]!.x += shifts[n.id]!.x; next[n.id]!.y += shifts[n.id]!.y }
  }
  positions.value = next; save(); fit()
}
function path(e: TopologyConnection, reverse = false, curved = false) {
  const source = reverse ? e.target : e.source, target = reverse ? e.source : e.target
  const a = point(source), b = point(target)
  const dx = b.x - a.x, dy = b.y - a.y, d = Math.max(1, Math.hypot(dx, dy)), ux = dx / d, uy = dy / d
  const lane = connectionLanes.value.get(e.id)
  const orientation = (e.source < e.target ? 1 : -1) * (reverse ? -1 : 1)
  const offset = (lane?.offset || 0) * orientation + (curved ? 32 : 0)
  const cx = (a.x + b.x) / 2 - uy * offset, cy = (a.y + b.y) / 2 + ux * offset
  const startDistance = Math.max(1, Math.hypot(cx - a.x, cy - a.y))
  const endDistance = Math.max(1, Math.hypot(cx - b.x, cy - b.y))
  const start = nodeRadius(source) + 3, end = nodeRadius(target) + 7
  const x = a.x + (cx - a.x) / startDistance * start, y = a.y + (cy - a.y) / startDistance * start
  const ex = b.x + (cx - b.x) / endDistance * end, ey = b.y + (cy - b.y) / endDistance * end
  return {
    d: offset ? `M ${x} ${y} Q ${cx} ${cy} ${ex} ${ey}` : `M ${x} ${y} L ${ex} ${ey}`,
    x: (x + 2 * cx + ex) / 4 - uy * 8, y: (y + 2 * cy + ey) / 4 + ux * 8,
  }
}
function connectionLabel(e: TopologyConnection) { return t('topology.pairNumber', { number: connectionLanes.value.get(e.id)?.index || 1 }) }
function clear() { selectedNode.value = ''; selectedEdge.value = ''; hoverEdge.value = '' }
function selectEdge(id: string) { if (suppressClick) return; selectedNode.value = ''; selectedEdge.value = id }
function selectNode(id: string) { if (suppressClick) return; selectedEdge.value = ''; selectedNode.value = id }
function focusNode(id: string) {
  selectNode(id); query.value = ''
  const p = positions.value[id]
  if (p) camera.value = { x: dimensions.value.width * .65 - p.x, y: dimensions.value.height / 2 - p.y, zoom: 1 }
}
function pointerDown(event: PointerEvent, id = '') {
  if (event.button !== 0 || !svg.value) return
  const start = id ? positions.value[id] : camera.value
  if (!start) return
  drag = { id, x: event.clientX, y: event.clientY, start: { ...start }, moved: false, pointer: event.pointerId }
  svg.value.setPointerCapture(event.pointerId)
}
function pointerMove(event: PointerEvent) {
  if (!drag) return
  const dx = event.clientX - drag.x, dy = event.clientY - drag.y
  if (Math.hypot(dx, dy) > 4) drag.moved = true
  if (drag.id) positions.value[drag.id] = { x: drag.start.x + dx / camera.value.zoom, y: drag.start.y + dy / camera.value.zoom }
  else camera.value = { ...camera.value, x: drag.start.x + dx, y: drag.start.y + dy }
}
function pointerUp() {
  if (!drag) return
  suppressClick = drag.moved
  if (drag.id && !drag.moved) selectNode(drag.id)
  if (drag.id) suppressClick = true
  if (svg.value?.hasPointerCapture(drag.pointer)) svg.value.releasePointerCapture(drag.pointer)
  if (drag.moved) save()
  drag = null
  setTimeout(() => { suppressClick = false }, 0)
}
function wheel(event: WheelEvent) {
  const old = camera.value, zoom = Math.max(.08, Math.min(3, old.zoom * Math.exp(-event.deltaY * .001)))
  camera.value = { x: event.clientX - (event.clientX - old.x) * zoom / old.zoom, y: event.clientY - (event.clientY - old.y) * zoom / old.zoom, zoom }
}
function zoomBy(factor: number) {
  const old = camera.value
  const zoom = Math.max(.08, Math.min(3, old.zoom * factor))
  const x = dimensions.value.width / 2, y = dimensions.value.height / 2
  camera.value = { x: x - (x - old.x) * zoom / old.zoom, y: y - (y - old.y) * zoom / old.zoom, zoom }
}
function nameLines(name: string, id: string) {
  const lines: string[] = []
  const limit = nodeRadius(id) * 1.45 / 16
  let line = '', width = 0
  for (const character of Array.from(name)) {
    const weight = /[\u0020-\u007e]/.test(character) ? .62 : 1
    if (line && width + weight > limit) { lines.push(line); line = ''; width = 0 }
    line += character; width += weight
  }
  if (line) lines.push(line)
  return lines
}
function nameFontSize(name: string, id: string) { return Math.min(16, nodeRadius(id) * 1.25 / Math.max(1, nameLines(name, id).length) / 1.2) }
function summary(value: string) {
  const values = value.split(',').map(x => x.trim())
  return values[0]!.slice(0, 24) + (values.length > 1 ? ` +${values.length - 1}` : '')
}
function reason(value: string) { return t('observation.' + (reasonKey[value] || 'none')) }
function date(value: string) { const number = Number(value); return number > 0 && number < 8640000000000 ? formatDateTime(new Date(number * 1000)) : t('common.none') }
function tint(id: string) { return colors.value[id] || '#278d8c' }
function nodeRadius(id: string) { const degree = degrees.value[id] || 0; return 43 + 14 * degree / (degree + 3) }
async function load() {
  if (busy.value || disposed) return
  busy.value = true
  try {
    const next = await request<TopologyBoard>(`/configs/${configId}/topology`)
    if (disposed) return
    const first = !board.value
    board.value = next; error.value = ''
    if (selectedNode.value && !next.nodes.some(n => n.id === selectedNode.value)) clear()
    if (selectedEdge.value && !next.connections.some(e => e.id === selectedEdge.value)) clear()
    const ids = new Set(next.nodes.map(n => n.id))
    positions.value = Object.fromEntries(Object.entries(positions.value).filter(([id]) => ids.has(id)))
    if (first && !Object.keys(positions.value).length) layout()
    else {
      next.nodes.forEach((n, i) => {
        if (!positions.value[n.id]) {
          const e = next.connections.find(e => e.source === n.id || e.target === n.id)
          const neighbor = e ? positions.value[e.source === n.id ? e.target : e.source] : undefined
          positions.value[n.id] = { x: (neighbor?.x || 0) + 160 * Math.cos(i * 2.4), y: (neighbor?.y || 0) + 160 * Math.sin(i * 2.4) }
        }
      })
      if (first) fit()
    }
  } catch (e) { error.value = e instanceof Error ? e.message : t('topology.loadFailed') }
  finally { busy.value = false }
}
const realtime = useRealtime(event => {
  if (event.payload.config_id !== configId && event.type !== 'config.list.updated') return
  if (['mesh.observation.updated', 'mesh.workspace.updated', 'config.overview.updated', 'runtime.snapshot.updated', 'config.list.updated'].includes(event.type)) {
    clearTimeout(timer)
    timer = setTimeout(() => { void load() }, 250)
  }
})
function visibility() {
  if (!document.hidden) void load()
}
function resize() { dimensions.value = { width: window.innerWidth, height: window.innerHeight } }
function keyboard(event: KeyboardEvent) {
  if (event.key === 'Escape') { clear(); query.value = ''; searchInput.value?.blur() }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchInput.value?.focus() }
}
function storage(event: StorageEvent) {
  if (event.key === 'wfm_access_token' && !readAuthToken()) { clear(); realtime.disconnect(); auth.clearAuth(); void router.replace({ path: '/login', query: { redirect: route.fullPath } }) }
  if (event.key === 'wfm_ui_theme_mode') preferences.applyUiTheme(normalizeThemeMode(event.newValue))
  if (event.key === 'wfm_ui_locale') void preferences.load(true)
}
onMounted(async () => {
  window.addEventListener('resize', resize); window.addEventListener('keydown', keyboard); window.addEventListener('storage', storage)
  document.addEventListener('visibilitychange', visibility)
  periodic = setInterval(() => { if (!document.hidden) void load() }, 60000)
  void preferences.load()
  void api.systemTimezone().then(value => setSystemTimeZone(value.timezone)).catch(() => {})
  await load()
  if (!disposed) realtime.connect()
})
onBeforeUnmount(() => {
  disposed = true; clearTimeout(timer); clearInterval(periodic); save()
  window.removeEventListener('resize', resize); window.removeEventListener('keydown', keyboard); window.removeEventListener('storage', storage)
  document.removeEventListener('visibilitychange', visibility)
})
</script>

<template>
  <main class="topology-board" :class="{ 'has-extended-legend': hasValidationErrors && hasDisabledElements }">
    <div class="board-atmosphere" aria-hidden="true" />
    <svg ref="svg" class="topology-canvas" :width="dimensions.width" :height="dimensions.height"
      :aria-label="t('topology.title')" @pointerdown="pointerDown($event)" @pointermove="pointerMove" @pointerup="pointerUp"
      @pointercancel="pointerUp" @wheel.prevent="wheel" @click.self="!suppressClick && clear()">
      <defs>
        <marker id="board-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" /></marker>
      </defs>
      <rect width="100%" height="100%" fill="transparent" @click="!suppressClick && clear()" />
      <g :transform="`translate(${camera.x} ${camera.y}) scale(${camera.zoom})`">
        <g v-for="e in connections" :key="e.id" class="topology-edge"
          :class="{ invalid: e.validation_errors.length > 0, healthy: e.health.state === 'healthy', unobserved: e.health.state === null, muted: selectedNode && e.source !== selectedNode && e.target !== selectedNode, disabled: !e.enabled }"
          @pointerenter="hoverEdge = e.id" @pointerleave="hoverEdge = ''" @pointerdown.stop @click.stop="selectEdge(e.id)">
          <title>{{ e.validation_errors.length ? e.validation_errors.map(message => translateMeshText(message, t)).join('\n') : reason(e.health.reason) }}</title>
          <path :d="path(e).d" class="edge-hit" @pointerdown.stop />
          <path v-if="expanded !== e.id" :d="path(e).d" class="edge-line" />
          <text v-if="expanded !== e.id && (connectionLanes.get(e.id)?.count || 0) > 1" :x="path(e).x" :y="path(e).y" class="edge-label">{{ connectionLabel(e) }}</text>
          <template v-if="expanded === e.id">
            <g v-for="(direction, i) in [e.forward, e.reverse]" :key="i">
              <template v-if="direction">
                <path :d="path(e, i === 1, true).d" class="edge-line expanded-line" marker-end="url(#board-arrow)" />
                <text :x="path(e, i === 1, true).x" :y="path(e, i === 1, true).y" class="edge-label">{{ summary(direction.allowed_ips) }}</text>
              </template>
            </g>
          </template>
        </g>
        <g v-for="n in nodes" :key="n.id" :transform="`translate(${point(n.id).x} ${point(n.id).y})`"
          class="topology-node" :style="{ '--node-color': tint(n.id) }" :class="{ selected: selectedNode === n.id || edge?.source === n.id || edge?.target === n.id, muted: selectedNode && !adjacent.has(n.id) && selectedNode !== n.id, disabled: !n.enabled }"
          role="button" tabindex="0" :aria-label="n.name" @keydown.enter.prevent="focusNode(n.id)" @pointerdown.stop="pointerDown($event, n.id)" @click.stop="selectNode(n.id)">
          <title>{{ n.name }}</title>
          <circle :r="nodeRadius(n.id) + 5" class="node-halo" />
          <circle :r="nodeRadius(n.id)" class="node-circle" />
          <text class="node-name" :style="{ fontSize: nameFontSize(n.name, n.id) + 'px' }"><tspan v-for="(line, i) in nameLines(n.name, n.id)" :key="i" x="0" :y="(i - (nameLines(n.name, n.id).length - 1) / 2) * nameFontSize(n.name, n.id) * 1.2 + nameFontSize(n.name, n.id) * .35">{{ line }}</tspan></text>
          <g :transform="`translate(${nodeRadius(n.id) * .58} ${nodeRadius(n.id) * .82})`" class="node-type" aria-hidden="true">
            <rect :x="n.node_type === 'dynamic' && n.endpoint_state && n.enabled ? -23 : -14" y="-13" :width="n.node_type === 'dynamic' && n.endpoint_state && n.enabled ? 46 : 28" height="26" rx="13" class="node-type-backdrop" />
            <component :is="n.node_type === 'dynamic' ? Connection : Monitor" :x="n.node_type === 'dynamic' && n.endpoint_state && n.enabled ? -16 : -8" y="-8" width="16" height="16" />
            <circle v-if="n.node_type === 'dynamic' && n.endpoint_state && n.enabled" cx="11" cy="0" r="4" class="node-status" :data-state="n.endpoint_state" />
          </g>
        </g>
      </g>
    </svg>
    <header class="board-toolbar">
      <div class="board-identity floating">
        <div class="brand-symbol"><el-icon><Files /></el-icon></div>
        <div class="board-heading"><span class="board-eyebrow">WG FREE MESH <span>/ {{ t('topology.title') }}</span></span><strong>{{ board?.config.name || '—' }}</strong></div>
        <span class="identity-divider" />
        <div class="board-count"><strong>{{ nodes.length }}</strong><span>{{ t('topology.nodeCount') }}</span></div>
        <div class="board-count"><strong>{{ connections.length }}</strong><span>{{ t('topology.linkCount') }}</span></div>
      </div>
      <div class="board-top-right">
        <span class="stream-state floating" :data-live="realtime.connected.value"><i />{{ t(realtime.connected.value ? 'topology.live' : 'topology.connecting') }}</span>
        <div class="board-search floating">
          <el-icon><Search /></el-icon><input ref="searchInput" v-model="query" :placeholder="t('topology.search')" :aria-label="t('topology.search')" /><kbd>{{ searchShortcut }}</kbd>
          <div v-if="results.length" class="search-results floating"><span class="board-eyebrow">{{ t('topology.searchResults') }}</span><button v-for="n in results" :key="n.id" @click="focusNode(n.id)"><span>{{ n.name }}</span><small>{{ n.virtual_ip }}</small></button></div>
        </div>
      </div>
    </header>
    <nav class="board-dock floating" :aria-label="t('topology.viewControls')">
      <div class="dock-zoom"><button :title="t('topology.zoomOut')" :aria-label="t('topology.zoomOut')" @click="zoomBy(1 / 1.2)"><el-icon><ZoomOut /></el-icon></button><span>{{ Math.round(camera.zoom * 100) }}<small>%</small></span><button :title="t('topology.zoomIn')" :aria-label="t('topology.zoomIn')" @click="zoomBy(1.2)"><el-icon><ZoomIn /></el-icon></button></div>
      <span class="dock-divider" />
      <button @click="fit"><el-icon><Aim /></el-icon><span>{{ t('topology.fit') }}</span></button>
    </nav>
    <aside v-if="node || edge" class="board-detail floating">
      <button class="close-detail" :aria-label="t('common.cancel')" @click="clear"><el-icon><Close /></el-icon></button>
      <template v-if="node">
        <span class="board-eyebrow">{{ t('topology.node') }}</span>
        <div class="detail-node-heading">
          <span class="detail-node-icon" :style="{ color: tint(node.id) }"><el-icon><component :is="node.node_type === 'dynamic' ? Connection : Monitor" /></el-icon></span>
          <div><h2>{{ node.name }}</h2><p>{{ t(node.node_type === 'dynamic' ? 'nodeWorkspace.dynamicNode' : 'nodeWorkspace.staticNode') }} · {{ t(node.enabled ? 'common.enabled' : 'common.disabled') }}</p></div>
        </div>
        <p v-if="node.endpoint_state" class="detail-status" :data-state="node.endpoint_state">{{ t('observation.' + node.endpoint_state) }}</p>
        <dl class="node-facts">
          <div><dt>{{ t('topology.virtualIp') }}</dt><dd>{{ node.virtual_ip || '—' }}</dd></div>
          <div><dt>IPv4</dt><dd>{{ node.ipv4_address || '—' }}</dd></div>
          <div><dt>IPv6</dt><dd>{{ node.ipv6_address || '—' }}</dd></div>
          <div v-if="node.wg_runtime_state"><dt>{{ t('topology.interface') }}</dt><dd>{{ t('endpointControl.' + (node.wg_runtime_state === 'running' ? 'wgRunning' : node.wg_runtime_state === 'stopped' ? 'wgStopped' : 'unknown')) }}</dd></div>
          <div v-if="node.config_sync_state"><dt>{{ t('topology.sync') }}</dt><dd>{{ t('topology.' + ({ in_sync: 'syncInSync', pending: 'syncPending', failed: 'syncFailed' }[node.config_sync_state] || 'syncUnknown')) }}</dd></div>
        </dl>
        <p v-if="node.tags.length" class="node-tags">{{ node.tags.join(' · ') }}</p>
        <label class="node-color">{{ t('topology.color') }}<input type="color" :value="tint(node.id)" @input="colors[node.id] = ($event.target as HTMLInputElement).value; save()" /><button @click="delete colors[node.id]; save()">{{ t('topology.reset') }}</button></label>
        <h3 class="related-heading">{{ t('topology.connections') }}<span>{{ related.length }}</span></h3>
        <button v-for="e in related" :key="e.id" class="related-row" @click="selectEdge(e.id)"><span class="related-name"><i :class="e.validation_errors.length ? 'invalid' : e.health.state || 'unobserved'" /><span>{{ nodeMap.get(e.source === node.id ? e.target : e.source)?.name }}<small>{{ connectionLabel(e) }} · {{ t(e.enabled ? 'common.enabled' : 'common.disabled') }}</small></span></span><span class="related-health" :class="e.validation_errors.length ? 'invalid' : e.health.state">{{ t(e.validation_errors.length ? 'topology.validationError' : e.health.state ? 'observation.' + e.health.state : 'topology.unobserved') }}<span aria-hidden="true">↗</span></span></button>
      </template>
      <template v-else-if="edge">
        <span class="board-eyebrow">{{ t('topology.connection') }}</span><h2>{{ nodeMap.get(edge.source)?.name }} ↔ {{ nodeMap.get(edge.target)?.name }}</h2>
        <p>{{ connectionLabel(edge) }} · {{ t(edge.enabled ? 'common.enabled' : 'common.disabled') }}</p>
        <p class="connection-id">{{ t('topology.groupId') }} · {{ edge.id }}</p>
        <template v-if="edge.validation_errors.length"><p class="invalid">{{ t('topology.validationError') }}</p><p v-for="message in edge.validation_errors" :key="message" class="validation-message">{{ translateMeshText(message, t) }}</p></template>
        <template v-else><p :class="edge.health.state">{{ t(edge.health.state ? 'observation.' + edge.health.state : 'topology.unobserved') }}</p><p>{{ reason(edge.health.reason) }}</p></template>
        <section v-for="(direction, i) in [edge.forward, edge.reverse]" :key="i" class="direction-detail">
          <template v-if="direction"><h3>{{ nodeMap.get(direction.local_node_id)?.name }} → {{ nodeMap.get(direction.peer_node_id)?.name }}</h3><dl><dt>AllowedIPs</dt><dd>{{ direction.allowed_ips }}</dd><dt>Endpoint</dt><dd>{{ translateMeshText(direction.endpoint_summary, t) || '—' }}</dd><dt>Keepalive</dt><dd>{{ direction.persistent_keepalive ?? '—' }}</dd><dt>{{ t('mesh.addressFamily') }}</dt><dd>{{ direction.endpoint_ref_family?.toUpperCase() || '—' }}</dd></dl></template>
          <p v-else>{{ t('topology.missingDirection') }}</p>
        </section>
        <p>PSK · {{ t(edge.has_preshared_key ? 'mesh.pskConfigured' : 'mesh.pskMissing') }}</p>
        <section v-for="sample in edge.health.observations" :key="sample.node_id" class="direction-detail">
          <h3>{{ t('observation.source') }} · {{ nodeMap.get(sample.node_id)?.name }}</h3>
          <template v-if="sample.peer"><dl><dt>{{ t('observation.handshake') }}</dt><dd>{{ date(sample.peer.latest_handshake) }}</dd><dt>{{ t('observation.rx') }}</dt><dd>{{ sample.peer.rx_bytes }}</dd><dt>{{ t('observation.tx') }}</dt><dd>{{ sample.peer.tx_bytes }}</dd></dl></template>
          <small>{{ t('observation.collected') }} · {{ formatDateTime(sample.observed_at) }}</small>
        </section>
      </template>
    </aside>
    <div v-if="error" class="board-feedback floating">{{ error }} <button @click="load">{{ t('common.refresh') }}</button></div>
    <div v-else-if="board?.issues.length" class="board-issues floating">{{ t('topology.invalidGroups', { count: board.issues.length }) }}</div>
    <div v-else-if="!board || !nodes.length" class="board-empty floating">{{ t(!board ? 'common.loading' : 'topology.empty') }}</div>
    <footer class="board-legend floating"><span><i class="legend-line healthy" />{{ t('observation.healthy') }}</span><span><i class="legend-line interrupted" />{{ t('observation.interrupted') }}</span><span><i class="legend-line unobserved" />{{ t('topology.unobserved') }}</span><span v-if="hasValidationErrors"><i class="legend-line invalid" />{{ t('topology.validationError') }}</span><span v-if="hasDisabledElements"><i class="legend-line disabled" />{{ t('common.disabled') }}</span></footer>
    <div class="board-signature" aria-hidden="true">WIREGUARD <span>/</span> AMNEZIAWG</div>
  </main>
</template>

<style scoped>
.topology-board {
  --board-paper:#f2f4f7;
  --board-glass:rgba(255,255,255,.96);
  --board-line:#e5e9ee;
  --board-grid:rgba(100,116,139,.12);
  --board-ink:#202c3d;
  --board-muted:#768295;
  --board-unobserved:#111827;
  --board-healthy:#25ab8b;
  --board-interrupted:#94a3b8;
  --board-invalid:#dc4446;
  --board-node:#ffffff;
  --board-node-shadow:rgba(25,44,61,.1);
  --board-shadow:0 2px 4px rgba(20,35,50,.02),0 12px 32px -16px rgba(20,35,50,.16);
  --board-selection-ink:#ffffff;
  position:fixed; inset:0; overflow:hidden; background:var(--board-paper); color:var(--board-ink);
  font-feature-settings:"ss01","cv11"; -webkit-font-smoothing:antialiased;
}
html[data-theme='dark'] .topology-board {
  --board-paper:#10161f; --board-glass:rgba(25,34,47,.97); --board-line:#2c3849;
  --board-grid:rgba(151,188,177,.14); --board-ink:#edf2fa; --board-muted:#9baabd; --board-node:#1b293a;
  --board-unobserved:#e2e8f0;
  --board-healthy:#3fc6a3; --board-interrupted:#8090a5;
  --board-invalid:#fb777c;
  --board-node-shadow:rgba(0,0,0,.28); --board-shadow:0 8px 32px -12px rgba(0,0,0,.4);
}
.board-atmosphere { position:absolute; inset:0; pointer-events:none; background-image:radial-gradient(var(--board-grid) .7px,transparent .7px),radial-gradient(ellipse at 60% 45%,var(--board-node),transparent 75%); background-size:24px 24px,100% 100%; }
.topology-canvas { position:absolute; inset:0; touch-action:none; user-select:none; }
.floating { background:var(--board-glass); border:1px solid var(--board-line); box-shadow:var(--board-shadow); backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px); border-radius:18px; }
button { display:inline-flex; align-items:center; justify-content:center; gap:8px; cursor:pointer; font:inherit; color:inherit; border:0; background:transparent; padding:9px 12px; border-radius:10px; transition:background .16s ease,color .16s ease; }
button:hover { background:color-mix(in srgb,var(--el-color-primary) 7%,transparent); color:var(--el-color-primary); }
button:focus-visible,input:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:4px; }
.topology-node,.topology-node:focus,.topology-node:focus-visible { outline:none!important; }
.topology-node:focus-visible .node-halo { stroke:var(--node-color); opacity:1; }
.board-toolbar { position:absolute; top:24px; left:24px; right:24px; display:flex; justify-content:space-between; align-items:center; gap:24px; pointer-events:none; z-index:3; }
.board-toolbar>* { pointer-events:auto; }
.board-identity { display:flex; align-items:center; gap:16px; padding:14px 16px; min-width:0; }
.brand-symbol { display:grid; place-items:center; flex-shrink:0; width:40px; height:40px; border-radius:12px; color:#fff; background:#168a83; font-size:23px; }
.board-heading { display:grid; gap:5px; min-width:115px; }
.board-eyebrow { font-size:10px; line-height:1.5; letter-spacing:.08em; color:var(--board-muted); font-weight:600; }
.board-eyebrow span { font-weight:400; letter-spacing:.02em; margin-left:5px; }
.board-heading strong { max-width:240px; font-size:18px; line-height:1.25; letter-spacing:-.025em; font-weight:650; overflow-wrap:anywhere; }
.identity-divider { width:1px; height:29px; background:var(--board-line); margin:0 2px 0 8px; }
.board-count { display:flex; align-items:baseline; gap:6px; text-align:center; }
.board-count strong { font-size:18px; font-weight:650; font-variant-numeric:tabular-nums; letter-spacing:-.03em; }
.board-count span { font-size:10px; color:var(--board-muted); white-space:nowrap; }
.board-top-right { display:flex; align-items:center; gap:12px; }
.board-search { position:relative; display:flex; align-items:center; gap:10px; padding:0 12px 0 15px; height:46px; border-radius:13px; }
.board-search>.el-icon { color:var(--board-muted); font-size:17px; }
.board-search>input { width:175px; border:0; outline:0; background:transparent; color:var(--board-ink); padding:10px 0; font:inherit; font-size:12px; }
.board-search>input::placeholder { color:var(--board-muted); }
.board-search kbd { border:1px solid var(--board-line); border-radius:5px; padding:2px 5px; color:var(--board-muted); font:10px system-ui; white-space:nowrap; }
.search-results { position:absolute; top:55px; right:0; width:300px; padding:14px; }
.search-results>.board-eyebrow { display:block; padding:0 8px 9px; }
.search-results button { display:flex; justify-content:space-between; text-align:left; width:100%; gap:16px; font-size:13px; padding:11px 9px; }
.search-results small { color:var(--board-muted); font-size:10px; font-variant-numeric:tabular-nums; }
.stream-state { display:flex; align-items:center; gap:7px; padding:11px 13px; border-radius:24px; font-size:11px; color:var(--board-muted); white-space:nowrap; }
.stream-state i { width:5px; height:5px; border-radius:50%; background:var(--board-muted); }
.stream-state[data-live='true'] i { background:var(--el-color-success); box-shadow:0 0 0 3px color-mix(in srgb,var(--el-color-success) 9%,transparent); }
.board-dock { position:absolute; left:50%; bottom:24px; transform:translateX(-50%); display:flex; align-items:center; gap:3px; height:50px; box-sizing:border-box; padding:5px 8px; border-radius:14px; z-index:3; }
.board-dock button { min-height:38px; font-size:12px; white-space:nowrap; padding:9px 11px; color:inherit; }
.board-dock button .el-icon { font-size:17px; }
.board-dock button:hover { color:var(--el-color-primary); background:color-mix(in srgb,var(--el-color-primary) 8%,transparent); }
.dock-divider { width:1px; height:20px; background:currentColor; opacity:.15; margin:0 7px; }
.dock-zoom { display:flex; align-items:center; gap:2px; }.dock-zoom>span { min-width:44px; font-size:12px; text-align:center; font-variant-numeric:tabular-nums; }.dock-zoom small { font-size:9px; color:var(--board-muted); padding-left:2px; }
.board-detail { position:absolute; top:116px; left:24px; width:296px; max-height:calc(100dvh - 212px); overflow:auto; padding:20px; overflow-wrap:anywhere; scrollbar-width:thin; scrollbar-color:var(--board-line) transparent; z-index:2; border-radius:18px; }
.board-detail>.board-eyebrow { display:block; padding-bottom:16px; color:var(--board-muted); font-size:11px; }
.board-detail h2 { margin:10px 16px 6px 0; font-size:22px; line-height:1.3; letter-spacing:-.025em; font-weight:650; }
.detail-node-heading { display:flex; gap:12px; align-items:center; margin:3px 0 14px; }
.detail-node-heading>div { min-width:0; }.detail-node-heading h2 { margin:0 0 4px; font-size:22px; }.detail-node-heading p { margin:0; font-size:11px; }
.detail-node-icon { flex-shrink:0; display:grid; place-items:center; width:44px; height:44px; border-radius:13px; background:color-mix(in srgb,currentColor 9%,var(--board-node)); font-size:23px; }
.board-detail h3 { font-size:13px; font-weight:650; margin:20px 0 12px; color:var(--board-ink); }
.board-detail p { font-size:12px; color:var(--board-muted); line-height:1.65; margin:7px 0; }
.close-detail { position:absolute; right:15px; top:16px; width:26px; height:26px; padding:4px; color:var(--board-muted); }
.board-detail dl { margin:20px 0; display:grid; grid-template-columns:minmax(75px,.8fr) minmax(0,1.2fr); gap:13px 14px; align-items:baseline; }
.board-detail dt { font-size:12px; color:var(--board-muted); line-height:1.65; }
.board-detail dd { margin:0; font-size:12px; line-height:1.65; white-space:pre-wrap; font-variant-numeric:tabular-nums; text-align:right; color:var(--board-ink); }
.board-detail .node-facts { display:block; background:color-mix(in srgb,var(--board-paper) 75%,var(--board-node)); padding:4px 12px; border-radius:12px; margin:16px 0 10px; }
.node-facts>div { display:grid; grid-template-columns:minmax(65px,.8fr) minmax(0,1.2fr); gap:12px; padding:10px 0; border-bottom:1px solid var(--board-line); }.node-facts>div:last-child { border:0; }
.node-facts dd { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:11px; }
.node-tags { padding:0 2px; }
.direction-detail { margin-top:19px; padding-top:1px; border-top:1px solid var(--board-line); }.direction-detail small { display:block; font-size:9px; color:var(--board-muted); line-height:1.8; }
.direction-detail dl { margin:12px 0; }
.node-color { display:flex; align-items:center; gap:9px; padding:10px 0; margin:8px 0 0; font-size:11px; color:var(--board-muted); }
.node-color input { appearance:none; -webkit-appearance:none; width:22px; height:22px; border:0; padding:0; background:transparent; cursor:pointer; }.node-color input::-webkit-color-swatch-wrapper { padding:2px; }.node-color input::-webkit-color-swatch { border:0; border-radius:50%; }.node-color input::-moz-color-swatch { border:0; border-radius:50%; }.node-color button { font-size:11px; padding:5px 7px; margin-left:auto; }
.related-heading { display:flex; align-items:center; justify-content:space-between; border-top:1px solid var(--board-line); padding-top:18px; }.related-heading>span { display:grid; place-items:center; min-width:22px; height:22px; border-radius:7px; background:var(--board-paper); color:var(--board-muted); font-size:11px; }
.related-row { width:100%; display:flex; justify-content:space-between; align-items:center; gap:12px; margin:7px 0 0; padding:11px 10px; border:1px solid var(--board-line); border-radius:10px; font-size:12px; text-align:left; background:transparent; }
.related-name { display:flex; align-items:center; gap:8px; min-width:0; overflow-wrap:anywhere; }.related-name i { width:6px; height:6px; flex-shrink:0; border-radius:50%; background:var(--board-interrupted); }.related-name i.healthy { background:var(--board-healthy); }.related-name i.unobserved { background:var(--board-unobserved); }
.related-health { display:flex; align-items:center; gap:8px; font-size:10px; color:var(--board-muted); white-space:nowrap; }.related-health>span { font-size:14px; }
.related-name small { display:block; margin-top:4px; font-size:10px; line-height:1.5; color:var(--board-muted); }
.related-name i.invalid,.legend-line.invalid { background:var(--board-invalid); }
.related-health.invalid,.board-detail .invalid { color:var(--board-invalid); }
.board-detail .validation-message { padding:10px; border-radius:8px; background:color-mix(in srgb,var(--board-invalid) 8%,var(--board-node)); color:var(--board-invalid); }
.board-detail .connection-id { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:10px; }
.healthy,.detail-status[data-state='online'] { color:var(--el-color-success)!important; }.detail-status[data-state='not_started'] { color:var(--el-color-warning)!important; }
.board-detail .detail-status { display:inline-flex; align-items:center; gap:7px; padding:5px 9px; margin:0; border-radius:7px; background:color-mix(in srgb,currentColor 7%,var(--board-node)); font-size:11px; }.detail-status::before { content:''; width:5px; height:5px; border-radius:50%; background:currentColor; }
.board-legend { position:absolute; left:24px; bottom:24px; display:flex; align-items:center; gap:18px; height:50px; box-sizing:border-box; padding:0 15px; border-radius:14px; font-size:11px; line-height:16px; color:var(--board-muted); pointer-events:none; }
.board-legend>span { display:inline-flex; align-items:center; gap:8px; white-space:nowrap; }
.legend-line { display:block; width:18px; height:2px; flex-shrink:0; border-radius:1px; background:var(--board-unobserved); }
.legend-line.healthy { background:var(--board-healthy); }.legend-line.interrupted { background:var(--board-interrupted); }
.legend-line.disabled { background:none; height:0; border-top:2px dashed var(--board-muted); border-radius:0; }
.board-signature { display:none; }
.edge-line { fill:none; stroke:var(--board-interrupted); stroke-width:2; opacity:.85; vector-effect:non-scaling-stroke; pointer-events:stroke; }
.healthy .edge-line { stroke:var(--board-healthy); }
.unobserved .edge-line { stroke:var(--board-unobserved); }
.expanded-line { stroke-width:2; opacity:1; }
.edge-hit { fill:none; stroke:transparent; stroke-width:20; cursor:pointer; vector-effect:non-scaling-stroke; }.disabled .edge-line { stroke-dasharray:5 5; }
.invalid .edge-line { stroke:var(--board-invalid); opacity:1; }
.edge-label { font-size:10px; font-weight:500; fill:var(--board-ink); text-anchor:middle; paint-order:stroke; stroke:var(--board-paper); stroke-width:6px; stroke-linejoin:round; cursor:pointer; font-variant-numeric:tabular-nums; }
.topology-node { cursor:grab; }.topology-node:active { cursor:grabbing; }
.node-circle { fill:color-mix(in srgb,var(--node-color) 4%,var(--board-node)); stroke:color-mix(in srgb,var(--node-color) 34%,var(--board-line)); stroke-width:1.5; filter:drop-shadow(0 4px 7px var(--board-node-shadow)); }
.node-halo { fill:none; stroke:transparent; stroke-width:7; pointer-events:none; }
.selected .node-halo { stroke:color-mix(in srgb,var(--node-color) 13%,transparent); }
.topology-node:hover .node-circle { stroke:var(--node-color); }
.selected .node-circle { fill:color-mix(in srgb,var(--node-color) 88%,#122c36); stroke:var(--node-color); stroke-width:1.5; }
.node-name { fill:var(--board-ink); font-size:16px; text-anchor:middle; pointer-events:none; font-weight:650; letter-spacing:-.02em; }
.selected .node-name { fill:var(--board-selection-ink); }
.node-type { color:var(--node-color); pointer-events:none; }
.node-type-backdrop { fill:var(--board-node); stroke:var(--board-line); stroke-width:1; filter:drop-shadow(0 2px 2px var(--board-node-shadow)); }
.node-type svg { fill:currentColor; }
.node-status { fill:#94a3b8; }
.node-status[data-state='online'] { fill:var(--el-color-success); }
.node-status[data-state='not_started'] { fill:var(--el-color-warning); }
.muted { opacity:.4; }
.topology-node.disabled .node-circle { stroke-dasharray:5 4; stroke:var(--node-color); }
.board-feedback,.board-empty { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); padding:22px 30px; font-size:13px; color:var(--board-muted); max-width:80vw; text-align:center; }
.board-feedback { color:var(--el-color-danger); }.board-feedback button { margin-left:8px; font-size:11px; }
.board-issues { position:absolute; right:32px; top:105px; padding:12px 16px; color:var(--board-invalid); font-size:11px; }
@media(max-width:1150px) { .board-top-right .stream-state { display:none; } }
@media(max-width:1440px) { .board-legend { bottom:86px; left:50%; transform:translateX(-50%); height:40px; }.board-detail { max-height:calc(100dvh - 258px); } }
@media(max-width:800px) { .board-toolbar { top:18px; left:18px; right:18px; gap:14px; }.board-identity { gap:11px; padding:12px; }.identity-divider,.board-count { display:none; }.board-heading strong { max-width:150px; font-size:17px; }.board-eyebrow span { display:none; }.board-search input { width:130px; }.board-search kbd { display:none; }.board-detail { left:18px; top:104px; width:296px; }.dock-divider { margin:0 3px; } }
@media(max-width:540px) {
  .board-toolbar { top:14px; left:14px; right:14px; gap:10px; }
  .board-identity { flex:1; }.board-heading { min-width:0; }.board-heading strong { max-width:130px; }
  .board-search { width:44px; box-sizing:border-box; padding:0 13px; border-radius:13px; }
  .board-search input { position:absolute; inset:0; width:100%; padding:0; opacity:0; }
  .board-search:focus-within { position:absolute; right:0; top:0; width:100%; z-index:4; padding-left:15px; }
  .board-search:focus-within input { position:static; width:100%; padding-right:12px; opacity:1; }
  .search-results { width:min(300px,calc(100vw - 28px)); box-sizing:border-box; top:57px; }
  .board-dock { height:46px; padding:4px 8px; bottom:14px; }.board-dock button { padding:8px; }.dock-zoom>span { min-width:38px; }
  .board-legend { bottom:72px; height:auto; min-height:36px; max-width:calc(100% - 28px); box-sizing:border-box; display:grid; grid-template-columns:repeat(2,max-content); gap:8px 16px; padding:10px 12px; font-size:10px; }.board-legend>span { gap:6px; }.legend-line { width:16px; }
  .board-detail { top:auto; bottom:148px; left:14px; right:14px; width:auto; max-height:min(47dvh,calc(100dvh - 256px)); padding:20px; }
  .has-extended-legend .board-detail { bottom:172px; max-height:min(47dvh,calc(100dvh - 280px)); }
  .board-issues { top:99px; right:14px; max-width:calc(100% - 28px); }.brand-symbol { width:36px; height:36px; }
}
@media(prefers-reduced-motion:reduce) { *,*::before,*::after { animation:none!important; transition:none!important; } }
</style>
