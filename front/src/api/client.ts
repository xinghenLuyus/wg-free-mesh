import axios, { AxiosError, AxiosHeaders } from 'axios'

import { API_BASE_URL } from '@/api/base'
import { hasTranslation, translate } from '@/i18n'
import type { ApiErrorResponse, ApiResponse } from '@/types/api'
import { clearAuthToken, readAuthToken } from '@/utils/authToken'
import { notify } from '@/utils/notify'

export class ApiClientError extends Error {
  code: string
  detail: Record<string, unknown>
  status: number

  constructor(message: string, code = 'REQUEST_FAILED', detail: Record<string, unknown> = {}, status = 0) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.detail = detail
    this.status = status
  }
}

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
})

function isCredentialUrl(url = '') {
  return url === '/auth/login' || url === '/auth/setup'
}

function isAuthFlowUrl(url = '') {
  return ['/auth/login', '/auth/setup', '/auth/session', '/auth/state', '/auth/logout'].includes(url)
}

function isSessionAuthError(code: string) {
  return ['AUTH_REQUIRED', 'AUTH_SETUP_REQUIRED', 'INVALID_TOKEN', 'TOKEN_EXPIRED'].includes(code)
}

function redirectForAuthError(code: string) {
  clearAuthToken()
  if (code === 'AUTH_SETUP_REQUIRED') {
    notify.warning(translate('errors.AUTH_SETUP_REQUIRED'))
    if (window.location.pathname !== '/setup') {
      window.location.assign('/setup')
    }
    return
  }
  notify.warning(translate('errors.TOKEN_EXPIRED'))
  if (window.location.pathname !== '/login') {
    const redirect = `${window.location.pathname}${window.location.search}`
    window.location.assign(`/login?redirect=${encodeURIComponent(redirect)}`)
  }
}

http.interceptors.request.use((config) => {
  const token = readAuthToken()
  if (token && !isCredentialUrl(config.url)) {
    const headers = AxiosHeaders.from(config.headers)
    headers.set('Authorization', `Bearer ${token}`)
    config.headers = headers
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (error instanceof AxiosError) {
      const data = error.response?.data as ApiErrorResponse | undefined
      const code = data?.error?.code || ''
      const url = error.config?.url || ''
      if (!isAuthFlowUrl(url) && isSessionAuthError(code)) {
        redirectForAuthError(code)
      }
    }
    return Promise.reject(error)
  },
)

function normalizeError(error: unknown): ApiClientError {
  if (error instanceof AxiosError) {
    const data = error.response?.data as ApiErrorResponse | undefined
    if (data?.error) {
      const translatedKey = `errors.${data.error.code}`
      const fallbackMessage =
        typeof data.error.detail?.message === 'string'
          ? data.error.detail.message
          : Array.isArray(data.error.detail?.errors) && data.error.detail.errors.length
            ? String((data.error.detail.errors[0] as { msg?: string }).msg || data.error.message)
            : data.error.message
      return new ApiClientError(
        hasTranslation(translatedKey) ? translate(translatedKey) : fallbackMessage,
        data.error.code,
        data.error.detail,
        error.response?.status ?? 0,
      )
    }
    return new ApiClientError(translate('errors.REQUEST_FAILED'), 'REQUEST_FAILED', {}, error.response?.status ?? 0)
  }
  if (error instanceof Error) {
    return new ApiClientError(error.message)
  }
  return new ApiClientError(translate('errors.REQUEST_FAILED'))
}

export async function request<T>(
  url: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
    data?: unknown
    responseType?: 'json' | 'blob'
    timeout?: number
  },
): Promise<T> {
  try {
    const response = await http.request<ApiResponse<T>>({
      url,
      method: options?.method ?? 'GET',
      data: options?.data,
      responseType: options?.responseType,
      timeout: options?.timeout,
    })
    if (options?.responseType === 'blob') {
      return response.data as T
    }
    return response.data.data
  } catch (error) {
    throw normalizeError(error)
  }
}
