import axios from 'axios'
import { useAuthStore } from '../store/authStore'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Access tokens are short-lived (30 min — see backend/.env.example) by
// design: a stolen one is only useful until it naturally expires, and
// there's no server-side revocation for it. That trade-off only works if
// the client silently exchanges the refresh token for a new access token
// on a 401, instead of just logging the user out — otherwise every real
// user gets kicked out every 30 minutes, which is not a trade a real
// customer would accept. This queues concurrent 401s behind a single
// in-flight refresh call rather than firing N parallel refresh requests
// (each of which would rotate the refresh token and invalidate the
// others — see the reuse-detection logic in backend/app/api/auth.py).
let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState()
  if (!refreshToken) return null

  try {
    const { data } = await axios.post(`${API_URL}/auth/refresh`, { refresh_token: refreshToken })
    setTokens(data)
    return data.access_token as string
  } catch {
    logout()
    return null
  }
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    const isAuthEndpoint = ['/auth/login', '/auth/signup', '/auth/refresh'].some((p) =>
      original?.url?.includes(p),
    )

    if (err.response?.status === 401 && !original?._retried && !isAuthEndpoint) {
      original._retried = true
      refreshPromise = refreshPromise ?? refreshAccessToken()
      const newToken = await refreshPromise
      refreshPromise = null

      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
    }

    return Promise.reject(err)
  },
)
