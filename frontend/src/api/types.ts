export interface Watchlist {
  id: string
  name: string
  created_at: string
}

export interface WatchlistItem {
  id: string
  symbol: string
  exchange: string
  added_at: string
}

export interface Quote {
  symbol: string
  price: number
  volume: number | null
  open: number | null
  high: number | null
  low: number | null
  prev_close: number | null
  exchange_ts: string
  source: string
  stale: boolean
  seconds_since_update: number
}

export interface Delta {
  symbol: string
  significant: boolean
  price_change_pct: number | null
  price_z_score: number | null
  volume_change_pct: number | null
  current_price: number | null
  last_seen_price: number | null
  last_viewed_at: string | null
  reason: string
  stale?: boolean
  source?: string
}

export interface Digest {
  watchlist_id: string
  generated_at: string
  content: string
  deltas: Delta[]
  ai_generated: boolean
}

export interface HistoryPoint {
  price: number
  exchange_ts: string
}

export interface NLAddResult {
  query: string
  matched_symbols: string[]
  added: WatchlistItem[]
  already_present: string[]
  ai_generated: boolean
  explanation: string
}
