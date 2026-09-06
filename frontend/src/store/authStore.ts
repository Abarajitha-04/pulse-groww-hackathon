import { create } from 'zustand'

const ACCESS_KEY = 'pulse_access_token'
const REFRESH_KEY = 'pulse_refresh_token'

interface TokenPair {
  access_token: string
  refresh_token: string
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  setTokens: (tokens: TokenPair) => void
  logout: () => void
}

// Note: browser storage here is fine — this is a real deployed app, not an
// in-conversation preview artifact, and these are exactly the kind of
// per-viewer state localStorage is for. The access token is short-lived
// (30 min); the refresh token is what api/client.ts's interceptor uses to
// silently get a new one instead of logging the user out every 30 minutes.
export const useAuthStore = create<AuthState>((set) => ({
  token: typeof window !== 'undefined' ? window.localStorage.getItem(ACCESS_KEY) : null,
  refreshToken: typeof window !== 'undefined' ? window.localStorage.getItem(REFRESH_KEY) : null,
  setTokens: ({ access_token, refresh_token }: TokenPair) => {
    window.localStorage.setItem(ACCESS_KEY, access_token)
    window.localStorage.setItem(REFRESH_KEY, refresh_token)
    set({ token: access_token, refreshToken: refresh_token })
  },
  logout: () => {
    window.localStorage.removeItem(ACCESS_KEY)
    window.localStorage.removeItem(REFRESH_KEY)
    set({ token: null, refreshToken: null })
  },
}))
