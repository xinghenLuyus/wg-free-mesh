import { computed, shallowRef } from 'vue'

type PendingMap = Record<string, boolean>

export function useAsyncActionGroup() {
  const pending = shallowRef<PendingMap>({})

  const isPending = (key: string) => computed(() => pending.value[key] === true)
  const hasPending = (key: string) => pending.value[key] === true

  async function run<T>(key: string, task: () => Promise<T>) {
    if (pending.value[key]) return undefined
    pending.value = { ...pending.value, [key]: true }
    try {
      return await task()
    } finally {
      const next = { ...pending.value }
      delete next[key]
      pending.value = next
    }
  }

  return {
    isPending,
    hasPending,
    run,
  }
}
