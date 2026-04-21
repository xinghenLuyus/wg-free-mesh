import { i18n, translate } from '@/i18n'

const DEFAULT_TIMEZONE = 'Asia/Shanghai'
let systemTimeZone = DEFAULT_TIMEZONE

function normalizeInput(value: string | Date | null | undefined) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function normalizeTimeZone(value: string | null | undefined) {
  const timezone = String(value || '').trim() || DEFAULT_TIMEZONE
  try {
    new Intl.DateTimeFormat(i18n.global.locale.value, { timeZone: timezone }).format(new Date())
    return timezone
  } catch {
    return DEFAULT_TIMEZONE
  }
}

export function setSystemTimeZone(value: string | null | undefined) {
  systemTimeZone = normalizeTimeZone(value)
}

export function getSystemTimeZone() {
  return systemTimeZone
}

export function formatDateTime(value: string | Date | null | undefined, fallback = translate('common.notAvailable')) {
  const date = normalizeInput(value)
  if (!date) return fallback
  return new Intl.DateTimeFormat(i18n.global.locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: systemTimeZone,
  }).format(date)
}
