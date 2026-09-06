import { create } from 'zustand'

const STORAGE_KEY = 'pulse_token'

interface AuthState {
  token: string | null
  setToken: (token: string) => void
  logout: () => void
}

// Note: browser storage here is fine — this is a real deployed app, not an
// in-conversation preview artifact, and a JWT is exactly the kind of
// per-viewer state localStorage is for.
export const useAuthStore = create<AuthState>((set) => ({
  token: typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null,
  setToken: (token: string) => {
    window.localStorage.setItem(STORAGE_KEY, token)
    set({ token })
  },
  logout: () => {
    window.localStorage.removeItem(STORAGE_KEY)
    set({ token: null })
  },
}))
