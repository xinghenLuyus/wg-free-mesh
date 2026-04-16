const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

function normalizeInput(value: string | Date | null | undefined) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value: string | Date | null | undefined, fallback = '暂无') {
  const date = normalizeInput(value)
  return date ? dateTimeFormatter.format(date) : fallback
}
