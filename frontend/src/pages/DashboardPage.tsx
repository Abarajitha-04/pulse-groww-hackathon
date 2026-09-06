import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createWatchlist, fetchDigest, fetchWatchlists, markSeen } from '../api/watchlists'
import { logoutServerSide } from '../api/auth'
import { WatchlistTable } from '../components/WatchlistTable'
import { DigestCard } from '../components/DigestCard'
import { ChatWidget } from '../components/ChatWidget'
import { useAuthStore } from '../store/authStore'

export function DashboardPage() {
  const [activeId, setActiveId] = useState<string | null>(null)
  const refreshToken = useAuthStore((s) => s.refreshToken)
  const logout = useAuthStore((s) => s.logout)
  const queryClient = useQueryClient()

  async function handleLogout() {
    if (refreshToken) await logoutServerSide(refreshToken)
    logout()
  }

  const watchlistsQuery = useQuery({ queryKey: ['watchlists'], queryFn: fetchWatchlists })

  useEffect(() => {
    if (!activeId && watchlistsQuery.data && watchlistsQuery.data.length > 0) {
      setActiveId(watchlistsQuery.data[0].id)
    }
  }, [watchlistsQuery.data, activeId])

  const createMutation = useMutation({
    mutationFn: (name: string) => createWatchlist(name),
    onSuccess: (wl) => {
      queryClient.invalidateQueries({ queryKey: ['watchlists'] })
      setActiveId(wl.id)
    },
  })

  const digestQuery = useQuery({
    queryKey: ['digest', activeId],
    queryFn: () => fetchDigest(activeId as string),
    enabled: !!activeId,
    refetchOnMount: true,
  })

  const markSeenMutation = useMutation({
    mutationFn: () => markSeen(activeId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['changes', activeId] })
    },
  })

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Pulse</h1>
          <p className="text-sm text-slate-500">What's changed since you last checked.</p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/settings" className="text-xs text-slate-400 hover:text-blue-600">
            Settings
          </Link>
          <button onClick={handleLogout} className="text-xs text-slate-400 hover:text-rose-600">
            Log out
          </button>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-2">
        {(watchlistsQuery.data ?? []).map((wl) => (
          <button
            key={wl.id}
            onClick={() => setActiveId(wl.id)}
            className={`rounded-full px-3 py-1 text-sm ${
              activeId === wl.id
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            {wl.name}
          </button>
        ))}
        <button
          onClick={() => createMutation.mutate('New Watchlist')}
          className="rounded-full border border-dashed border-slate-300 px-3 py-1 text-sm text-slate-500 hover:border-blue-500 hover:text-blue-600 dark:border-slate-700"
        >
          + New watchlist
        </button>
      </div>

      {activeId ? (
        <div className="space-y-6">
          <DigestCard digest={digestQuery.data} loading={digestQuery.isLoading} />
          <WatchlistTable watchlistId={activeId} />
          <button
            onClick={() => markSeenMutation.mutate()}
            className="w-full rounded-xl border border-slate-200 py-2 text-sm text-slate-500 hover:border-blue-500 hover:text-blue-600 dark:border-slate-800"
          >
            Mark everything as seen
          </button>
          <p className="text-center text-xs text-slate-400">
            "Mark as seen" is a deliberate, explicit action here — not automatic on page load —
            so opening the app doesn't erase a delta before you've actually read it.
          </p>
        </div>
      ) : (
        <p className="text-slate-400">Create a watchlist to get started.</p>
      )}

      <ChatWidget />
    </div>
  )
}
