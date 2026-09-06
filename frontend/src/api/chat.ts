import { api } from './client'
import type { ChatMessage, ChatResponse } from './types'

export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const { data } = await api.get('/chat/history')
  return data
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const { data } = await api.post('/chat', { message })
  return data
}

export async function clearChatHistory(): Promise<void> {
  await api.delete('/chat/history')
}
