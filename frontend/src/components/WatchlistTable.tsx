import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { addItem, addItemsNaturalLanguage, fetchChanges, fetchItems, removeItem } from '../api/watchlists'
import { DeltaBadge } from './DeltaBadge'
import { StalenessIndicator } from './StalenessIndicator'
import { Sparkline } from './Sparkline'
import { useLiveQuotes } from '../hooks/useLiveQuotes'

export function WatchlistTable({ watchlistId }: { watchlistId: string }) {
  const [symbolInput, setSymbolInput] = useState('')
  const [nlMode, setNlMode] = useState(false)
  const [nlQuery, setNlQuery] = useState('')
  const [nlResult, setNlResult] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const itemsQuery = useQuery({
    queryKey: ['items', watchlistId],
    queryFn: () => fetchItems(watchlistId),
  })

  const changesQuery = useQuery({
    queryKey: ['changes', watchlistId],
    queryFn: () => fetchChanges(watchlistId),
    // Poll fallback — works even if the WebSocket never connects.
    refetchInterval: 15000,
    enabled: (itemsQuery.data?.length ?? 0) > 0,
  })

  const symbols = itemsQuery.data?.map((i) => i.symbol) ?? []
  const { quotes, connected } = useLiveQuotes(symbols)

  const addMutation = useMutation({
    mutationFn: (symbol: string) => addItem(watchlistId, symbol.trim().toUpperCase()),
    onSuccess: () => {
      setSymbolInput('')
      queryClient.invalidateQueries({ queryKey: ['items', watchlistId] })
    },
  })

  const removeMutation = useMutation({
    mutationFn: (symbol: string) => removeItem(watchlistId, symbol),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items', watchlistId] }),
  })

  const nlMutation = useMutation({
    mutationFn: (query: string) => addItemsNaturalLanguage(watchlistId, query),
    onSuccess: (result) => {
      setNlQuery('')
      queryClient.invalidateQueries({ queryKey: ['items', watchlistId] })
      const addedCount = result.added.length
      const badge = result.ai_generated ? 'AI' : 'keyword match — no AI key set'
      setNlResult(
        addedCount > 0
          ? `Added ${addedCount} symbol${addedCount > 1 ? 's' : ''} (${badge}): ${result.explanation}`
          : `No new symbols matched (${badge}): ${result.explanation}`,
      )
    },
  })

  const deltaBySymbol = Object.fromEntries((changesQuery.data ?? []).map((d) => [d.symbol, d]))

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-100 p-4 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">Symbols</h2>
          <span
            className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-slate-300'}`}
            title={connected ? 'Live updates connected' : 'Live updates offline — polling instead'}
          />
        </div>
        <div className="flex items-center gap-2">
          {nlMode ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (nlQuery.trim()) nlMutation.mutate(nlQuery)
              }}
              className="flex gap-2"
            >
              <input
                value={nlQuery}
                onChange={(e) => setNlQuery(e.target.value)}
                placeholder='e.g. "top 3 FMCG large-caps"'
                className="w-56 rounded-lg border border-violet-300 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-violet-500 dark:border-violet-800"
              />
              <button
                type="submit"
                disabled={nlMutation.isPending}
                className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
              >
                {nlMutation.isPending ? '…' : '✨ Add'}
              </button>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (symbolInput.trim()) addMutation.mutate(symbolInput)
              }}
              className="flex gap-2"
            >
              <input
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="e.g. RELIANCE.NS"
                className="rounded-lg border border-slate-300 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-blue-500 dark:border-slate-700"
              />
              <button
                type="submit"
                disabled={addMutation.isPending}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Add
              </button>
            </form>
          )}
          <button
            type="button"
            onClick={() => {
              setNlMode((m) => !m)
              setNlResult(null)
            }}
            className="text-xs text-slate-400 hover:text-violet-600"
            title="Toggle natural-language add"
          >
            {nlMode ? 'use symbol' : '✨ describe it'}
          </button>
        </div>
      </div>

      {addMutation.isError && (
        <p className="px-4 pt-2 text-xs text-rose-600">
          {(addMutation.error as any)?.response?.data?.detail ?? 'Could not add symbol'}
        </p>
      )}
      {nlResult && <p className="px-4 pt-2 text-xs text-violet-600">{nlResult}</p>}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase text-slate-400">
            <th className="px-4 py-2">Symbol</th>
            <th className="px-4 py-2">Price</th>
            <th className="px-4 py-2">30-pt trend</th>
            <th className="px-4 py-2">Since you last checked</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody>
          {(itemsQuery.data ?? []).map((item) => {
            const liveQuote = quotes[item.symbol]
            const delta = deltaBySymbol[item.symbol]
            const price = liveQuote?.price ?? delta?.current_price
            return (
              <tr key={item.id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="px-4 py-3 font-medium">{item.symbol}</td>
                <td className="px-4 py-3">
                  {price !== undefined && price !== null ? (
                    <span className="flex items-center gap-2">
                      ₹{Number(price).toFixed(2)}
                      <StalenessIndicator stale={liveQuote?.stale ?? delta?.stale} source={delta?.source} />
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Sparkline symbol={item.symbol} />
                </td>
                <td className="px-4 py-3">{delta ? <DeltaBadge delta={delta} /> : '—'}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => removeMutation.mutate(item.symbol)}
                    className="text-xs text-slate-400 hover:text-rose-600"
                  >
                    remove
                  </button>
                </td>
              </tr>
            )
          })}
          {itemsQuery.data?.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                No symbols yet — add one above to start tracking.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
