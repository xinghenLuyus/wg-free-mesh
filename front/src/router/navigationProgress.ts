import { shallowRef } from 'vue'

export const navigationPending = shallowRef(false)

let progressTimer: ReturnType<typeof setTimeout> | undefined
let finishFadeOut: ((completed: boolean) => void) | undefined

export function startNavigationProgress() {
  finishNavigationProgress()
  progressTimer = setTimeout(() => {
    navigationPending.value = true
    progressTimer = undefined
  }, 120)
}

export function finishNavigationProgress() {
  if (progressTimer) clearTimeout(progressTimer)
  progressTimer = undefined
  navigationPending.value = false
}

export function waitForPageFadeOut(): Promise<boolean> {
  cancelPageFadeOut()
  return new Promise((resolve) => {
    let fallbackTimer: ReturnType<typeof setTimeout>
    const complete = (completed: boolean) => {
      clearTimeout(fallbackTimer)
      if (finishFadeOut === complete) finishFadeOut = undefined
      resolve(completed)
    }
    finishFadeOut = complete
    fallbackTimer = setTimeout(() => complete(true), 400)
  })
}

export function completePageFadeOut() {
  finishFadeOut?.(true)
}

export function cancelPageFadeOut() {
  finishFadeOut?.(false)
}
