import axios, { AxiosError, AxiosHeaders } from 'axios'

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
  baseURL: '/api/v1',
  timeout: 20000,
})

function isCredentialUrl(url = '') {
  return url === '/auth/login' || url === '/auth/setup'
}

function isAuthFlowUrl(url = '') {
  return ['/auth/login', '/auth/setup', '/auth/session', '/auth/state', '/auth/logout'].includes(url)
}

function redirectForAuthError(code: string) {
  clearAuthToken()
  if (code === 'AUTH_SETUP_REQUIRED') {
    notify.warning('需要先设置初始管理员密码')
    if (window.location.pathname !== '/setup') {
      window.location.assign('/setup')
    }
    return
  }
  notify.warning('登录状态已失效，请重新登录')
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
      const status = error.response?.status || 0
      const url = error.config?.url || ''
      if (!isAuthFlowUrl(url) && (status === 401 || code === 'AUTH_SETUP_REQUIRED')) {
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
      return new ApiClientError(data.error.message, data.error.code, data.error.detail, error.response?.status ?? 0)
    }
    return new ApiClientError(error.message, 'REQUEST_FAILED', {}, error.response?.status ?? 0)
  }
  if (error instanceof Error) {
    return new ApiClientError(error.message)
  }
  return new ApiClientError('请求失败')
}

export async function request<T>(
  url: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
    data?: unknown
    responseType?: 'json' | 'blob'
  },
): Promise<T> {
  try {
    const response = await http.request<ApiResponse<T>>({
      url,
      method: options?.method ?? 'GET',
      data: options?.data,
      responseType: options?.responseType,
    })
    if (options?.responseType === 'blob') {
      return response.data as T
    }
    return response.data.data
  } catch (error) {
    throw normalizeError(error)
  }
}
