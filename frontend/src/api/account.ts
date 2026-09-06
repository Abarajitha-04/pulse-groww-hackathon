import { api } from './client'

export interface Me {
  id: string
  email: string
  created_at: string
  alerts_enabled: boolean
}

export async function fetchMe(): Promise<Me> {
  const { data } = await api.get('/users/me')
  return data
}

export async function updateAlertsEnabled(alerts_enabled: boolean): Promise<Me> {
  const { data } = await api.patch('/users/me/settings', { alerts_enabled })
  return data
}

export async function exportMyData(): Promise<unknown> {
  const { data } = await api.get('/users/me/export')
  return data
}

export async function deleteMyAccount(password: string): Promise<void> {
  await api.delete('/users/me', { data: { password } })
}
