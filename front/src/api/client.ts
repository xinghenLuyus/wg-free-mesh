import axios, { AxiosError } from 'axios'

import type { ApiErrorResponse, ApiResponse } from '@/types/api'

export class ApiClientError extends Error {
  code: string
  detail: Record<string, unknown>

  constructor(message: string, code = 'REQUEST_FAILED', detail: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.detail = detail
  }
}

export const http = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  timeout: 20000,
})

function normalizeError(error: unknown): ApiClientError {
  if (error instanceof AxiosError) {
    const data = error.response?.data as ApiErrorResponse | undefined
    if (data?.error) {
      return new ApiClientError(data.error.message, data.error.code, data.error.detail)
    }
    return new ApiClientError(error.message)
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
