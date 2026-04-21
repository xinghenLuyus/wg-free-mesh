import { translate } from '@/i18n'

type NotifyType = 'success' | 'warning' | 'info' | 'error'

const titleKeys: Record<NotifyType, string> = {
  success: 'notify.success',
  warning: 'notify.warning',
  info: 'notify.info',
  error: 'notify.error',
}

function ensureContainer() {
  const existing = document.getElementById('app-toast-container')
  if (existing) return existing

  const container = document.createElement('div')
  container.id = 'app-toast-container'
  container.setAttribute('aria-live', 'polite')
  document.body.appendChild(container)
  return container
}

function open(type: NotifyType, message: string, duration = type === 'error' ? 7000 : 4200) {
  const container = ensureContainer()
  const toast = document.createElement('section')
  const title = document.createElement('strong')
  const content = document.createElement('div')
  const mark = document.createElement('span')
  const close = document.createElement('button')
  const closeText = document.createElement('span')
  const progress = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  const progressRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')

  let remaining = duration
  let startedAt = 0
  let timerId: number | undefined
  let closed = false

  toast.className = `app-toast app-toast--${type}`
  toast.style.setProperty('--toast-duration', `${duration}ms`)
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status')

  mark.className = 'app-toast__mark'
  mark.setAttribute('aria-hidden', 'true')

  title.className = 'app-toast__title'
  title.textContent = translate(titleKeys[type])

  content.className = 'app-toast__content'
  content.textContent = message

  progress.classList.add('app-toast__progress')
  progress.setAttribute('viewBox', '0 0 28 28')
  progress.setAttribute('aria-hidden', 'true')
  progressRect.classList.add('app-toast__progress-rect')
  progressRect.setAttribute('x', '2')
  progressRect.setAttribute('y', '2')
  progressRect.setAttribute('width', '24')
  progressRect.setAttribute('height', '24')
  progressRect.setAttribute('rx', '6')
  progressRect.setAttribute('pathLength', '100')
  progress.appendChild(progressRect)

  close.className = 'app-toast__close'
  close.type = 'button'
  close.setAttribute('aria-label', translate('notify.close'))
  closeText.className = 'app-toast__close-text'
  closeText.textContent = '×'
  close.append(progress, closeText)

  const body = document.createElement('div')
  body.className = 'app-toast__body'
  body.append(title, content)
  toast.append(mark, body, close)

  function remove() {
    if (closed) return
    closed = true
    if (timerId) window.clearTimeout(timerId)
    toast.classList.add('app-toast--leaving')
    window.setTimeout(() => toast.remove(), 260)
  }

  function startTimer() {
    if (duration <= 0 || closed) return
    startedAt = Date.now()
    timerId = window.setTimeout(remove, remaining)
  }

  function pauseTimer() {
    if (!timerId || closed) return
    window.clearTimeout(timerId)
    timerId = undefined
    remaining = Math.max(0, remaining - (Date.now() - startedAt))
    toast.classList.add('app-toast--paused')
  }

  function resumeTimer() {
    if (timerId || remaining <= 0 || closed) return
    toast.classList.remove('app-toast--paused')
    startTimer()
  }

  close.addEventListener('click', remove)
  toast.addEventListener('mouseenter', pauseTimer)
  toast.addEventListener('mouseleave', resumeTimer)

  container.appendChild(toast)
  startTimer()
}

export const notify = {
  success: (message: string, duration?: number) => open('success', message, duration),
  warning: (message: string, duration?: number) => open('warning', message, duration),
  info: (message: string, duration?: number) => open('info', message, duration),
  error: (message: string, duration?: number) => open('error', message, duration),
}
