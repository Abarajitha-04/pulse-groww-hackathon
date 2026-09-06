import { api } from './client'

export async function signup(email: string, password: string) {
  const { data } = await api.post('/auth/signup', { email, password })
  return data.access_token as string
}

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password })
  return data.access_token as string
}
