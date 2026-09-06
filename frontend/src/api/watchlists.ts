import { api } from './client'
import type { Watchlist, WatchlistItem, Delta, Digest, HistoryPoint, NLAddResult } from './types'

export async function fetchWatchlists(): Promise<Watchlist[]> {
  const { data } = await api.get('/watchlists')
  return data
}

export async function createWatchlist(name: string): Promise<Watchlist> {
  const { data } = await api.post('/watchlists', { name })
  return data
}

export async function fetchItems(watchlistId: string): Promise<WatchlistItem[]> {
  const { data } = await api.get(`/watchlists/${watchlistId}/items`)
  return data
}

export async function addItem(watchlistId: string, symbol: string, exchange = 'NSE'): Promise<WatchlistItem> {
  const { data } = await api.post(`/watchlists/${watchlistId}/items`, { symbol, exchange })
  return data
}

export async function addItemsNaturalLanguage(watchlistId: string, query: string): Promise<NLAddResult> {
  const { data } = await api.post(`/watchlists/${watchlistId}/items/natural-language`, { query })
  return data
}

export async function removeItem(watchlistId: string, symbol: string): Promise<void> {
  await api.delete(`/watchlists/${watchlistId}/items/${symbol}`)
}

export async function fetchChanges(watchlistId: string): Promise<Delta[]> {
  const { data } = await api.get(`/watchlists/${watchlistId}/changes`)
  return data
}

export async function markSeen(watchlistId: string): Promise<void> {
  await api.post(`/watchlists/${watchlistId}/mark-seen`)
}

export async function fetchDigest(watchlistId: string): Promise<Digest> {
  const { data } = await api.get(`/watchlists/${watchlistId}/digest`)
  return data
}

export async function fetchHistory(symbol: string, limit = 30): Promise<HistoryPoint[]> {
  const { data } = await api.get(`/market/history/${symbol}`, { params: { limit } })
  return data.points
}
