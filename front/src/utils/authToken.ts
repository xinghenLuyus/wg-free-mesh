const AUTH_TOKEN_KEY = 'wfm_access_token'

export function readAuthToken() {
  return window.localStorage.getItem(AUTH_TOKEN_KEY) || ''
}

export function writeAuthToken(token: string) {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
}

export function clearAuthToken() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
}
