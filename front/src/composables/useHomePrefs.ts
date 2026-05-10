import { shallowRef, watch } from 'vue'

export type HomeStatusFilter = 'all' | 'enabled' | 'disabled'
export type HomeSortKey = 'updated' | 'name' | 'nodes' | 'online'
export type HomeLayoutMode = 'grid' | 'list'

interface HomePrefs {
  statusFilter: HomeStatusFilter
  sortKey: HomeSortKey
  layoutMode: HomeLayoutMode
}

const STORAGE_KEY = 'wfm:home-prefs'
const DEFAULT_PREFS: HomePrefs = {
  statusFilter: 'all',
  sortKey: 'updated',
  layoutMode: 'grid',
}

const STATUS_FILTERS = new Set<HomeStatusFilter>(['all', 'enabled', 'disabled'])
const SORT_KEYS = new Set<HomeSortKey>(['updated', 'name', 'nodes', 'online'])
const LAYOUT_MODES = new Set<HomeLayoutMode>(['grid', 'list'])

function normalizePrefs(payload: unknown): HomePrefs {
  if (!payload || typeof payload !== 'object') return { ...DEFAULT_PREFS }
  const candidate = payload as Partial<HomePrefs>
  return {
    statusFilter: STATUS_FILTERS.has(candidate.statusFilter as HomeStatusFilter)
      ? (candidate.statusFilter as HomeStatusFilter)
      : DEFAULT_PREFS.statusFilter,
    sortKey: SORT_KEYS.has(candidate.sortKey as HomeSortKey) ? (candidate.sortKey as HomeSortKey) : DEFAULT_PREFS.sortKey,
    layoutMode: LAYOUT_MODES.has(candidate.layoutMode as HomeLayoutMode) ? (candidate.layoutMode as HomeLayoutMode) : DEFAULT_PREFS.layoutMode,
  }
}

function readPrefs(): HomePrefs {
  if (typeof window === 'undefined') return { ...DEFAULT_PREFS }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? normalizePrefs(JSON.parse(raw)) : { ...DEFAULT_PREFS }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export function useHomePrefs() {
  const prefs = readPrefs()
  const statusFilter = shallowRef<HomeStatusFilter>(prefs.statusFilter)
  const sortKey = shallowRef<HomeSortKey>(prefs.sortKey)
  const layoutMode = shallowRef<HomeLayoutMode>(prefs.layoutMode)

  watch(
    [statusFilter, sortKey, layoutMode],
    ([nextStatusFilter, nextSortKey, nextLayoutMode]) => {
      if (typeof window === 'undefined') return
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          statusFilter: nextStatusFilter,
          sortKey: nextSortKey,
          layoutMode: nextLayoutMode,
        } satisfies HomePrefs),
      )
    },
    { flush: 'post' },
  )

  return {
    statusFilter,
    sortKey,
    layoutMode,
  }
}
