function normalizeBaseOrigin(origin: string) {
  return origin.endsWith('/') ? origin.slice(0, -1) : origin
}

function defaultApiOrigin() {
  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8000'
  }
  if (window.location.port === '5173') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return window.location.origin
}

const configuredOrigin = String(import.meta.env.VITE_API_BASE_URL || '').trim()
export const API_ORIGIN = normalizeBaseOrigin(configuredOrigin || defaultApiOrigin())
export const API_BASE_URL = `${API_ORIGIN}/api/v1`
export const REALTIME_STREAM_URL = `${API_BASE_URL}/events/stream`
