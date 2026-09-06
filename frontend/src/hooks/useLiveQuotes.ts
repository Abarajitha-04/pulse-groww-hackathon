import { useEffect, useRef, useState } from 'react'
import { API_URL } from '../api/client'
import type { Quote } from '../api/types'

/**
 * Live tick subscription over WebSocket, with a polling-shaped fallback
 * contract: if the socket never connects or drops, callers still have
 * `quotes` populated by whatever the last REST fetch put there (the
 * WatchlistTable component fetches once via React Query regardless of
 * socket state) — the UI never depends on the socket to be usable, only
 * to feel live.
 */
export function useLiveQuotes(symbols: string[]) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (symbols.length === 0) return

    const wsUrl = API_URL.replace('http', 'ws') + `/ws/prices?symbols=${symbols.join(',')}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        setQuotes((prev) => ({ ...prev, [payload.symbol]: payload.quote }))
      } catch {
        // Malformed frame — ignore rather than crash the socket handler.
      }
    }

    return () => {
      ws.close()
    }
  }, [symbols.join(',')])

  return { quotes, connected }
}
