import { api } from './client'

export interface TokenPair {
  access_token: string
  refresh_token: string
}

export async function signup(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post('/auth/signup', { email, password })
  return data
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post('/auth/login', { email, password })
  return data
}

export async function logoutServerSide(refreshToken: string): Promise<void> {
  // Best-effort: the local logout (clearing stored tokens) must always
  // succeed even if this call fails (network down, token already
  // expired) — this just also revokes the refresh token server-side so
  // it can't be replayed later.
  try {
    await api.post('/auth/logout', { refresh_token: refreshToken })
  } catch {
    // intentionally ignored — see comment above
  }
}
