import { computed, shallowRef, watch, type Ref } from 'vue'

type ViewMode = 'grid' | 'list'
type SortKey = 'name' | 'virtual_ip' | 'created_at' | 'online' | 'node_type'

interface ConfigOverviewPrefs {
  viewMode: ViewMode
  sortKey: SortKey
  tagFilter: string
}

const DEFAULT_PREFS: ConfigOverviewPrefs = {
  viewMode: 'grid',
  sortKey: 'name',
  tagFilter: '',
}

const VIEW_MODES = new Set<ViewMode>(['grid', 'list'])
const SORT_KEYS = new Set<SortKey>(['name', 'virtual_ip', 'created_at', 'online', 'node_type'])

function storageKey(configId: string) {
  return `wfm:config-overview-prefs:${configId}`
}

function normalizePrefs(payload: unknown): ConfigOverviewPrefs {
  if (!payload || typeof payload !== 'object') return { ...DEFAULT_PREFS }
  const candidate = payload as Partial<ConfigOverviewPrefs>
  return {
    viewMode: VIEW_MODES.has(candidate.viewMode as ViewMode) ? (candidate.viewMode as ViewMode) : DEFAULT_PREFS.viewMode,
    sortKey: SORT_KEYS.has(candidate.sortKey as SortKey) ? (candidate.sortKey as SortKey) : DEFAULT_PREFS.sortKey,
    tagFilter: typeof candidate.tagFilter === 'string' ? candidate.tagFilter : DEFAULT_PREFS.tagFilter,
  }
}

function readPrefs(configId: string): ConfigOverviewPrefs {
  if (!configId || typeof window === 'undefined') return { ...DEFAULT_PREFS }
  try {
    const raw = window.localStorage.getItem(storageKey(configId))
    return raw ? normalizePrefs(JSON.parse(raw)) : { ...DEFAULT_PREFS }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export function useConfigOverviewPrefs(configId: Ref<string>) {
  const viewMode = shallowRef<ViewMode>(DEFAULT_PREFS.viewMode)
  const sortKey = shallowRef<SortKey>(DEFAULT_PREFS.sortKey)
  const tagFilter = shallowRef(DEFAULT_PREFS.tagFilter)

  const currentStorageKey = computed(() => storageKey(configId.value))

  watch(
    configId,
    (nextConfigId) => {
      const prefs = readPrefs(nextConfigId)
      viewMode.value = prefs.viewMode
      sortKey.value = prefs.sortKey
      tagFilter.value = prefs.tagFilter
    },
    { immediate: true },
  )

  watch(
    [currentStorageKey, viewMode, sortKey, tagFilter],
    ([nextStorageKey, nextViewMode, nextSortKey, nextTagFilter]) => {
      if (typeof window === 'undefined' || !configId.value) return
      window.localStorage.setItem(
        nextStorageKey,
        JSON.stringify({
          viewMode: nextViewMode,
          sortKey: nextSortKey,
          tagFilter: nextTagFilter,
        } satisfies ConfigOverviewPrefs),
      )
    },
    { flush: 'post' },
  )

  return {
    viewMode,
    sortKey,
    tagFilter,
  }
}
