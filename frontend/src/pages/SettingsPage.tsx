import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteMyAccount, exportMyData, fetchMe, updateAlertsEnabled } from '../api/account'
import { useAuthStore } from '../store/authStore'

export function SettingsPage() {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const meQuery = useQuery({ queryKey: ['me'], queryFn: fetchMe })

  const alertsMutation = useMutation({
    mutationFn: (enabled: boolean) => updateAlertsEnabled(enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['me'] }),
  })

  const exportMutation = useMutation({
    mutationFn: exportMyData,
    onSuccess: (data) => {
      // Client-side download only — nothing is sent anywhere but the
      // user's own browser downloads folder.
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'pulse-data-export.json'
      a.click()
      URL.revokeObjectURL(url)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (pw: string) => deleteMyAccount(pw),
    onSuccess: () => {
      logout()
      navigate('/auth')
    },
    onError: (err: any) => {
      setDeleteError(err?.response?.data?.detail ?? 'Could not delete account')
    },
  })

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold">Settings</h1>
        <Link to="/" className="text-xs text-slate-400 hover:text-blue-600">
          Back to dashboard
        </Link>
      </div>

      <div className="space-y-6">
        <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
          <h2 className="mb-1 text-sm font-semibold">Account</h2>
          <p className="text-sm text-slate-500">{meQuery.data?.email}</p>
        </section>

        <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
          <h2 className="mb-2 text-sm font-semibold">Notifications</h2>
          <label className="flex items-center justify-between text-sm">
            <span>Email me when a watched stock moves significantly</span>
            <input
              type="checkbox"
              checked={meQuery.data?.alerts_enabled ?? false}
              onChange={(e) => alertsMutation.mutate(e.target.checked)}
              className="h-4 w-4"
            />
          </label>
        </section>

        <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
          <h2 className="mb-2 text-sm font-semibold">Your data</h2>
          <p className="mb-3 text-xs text-slate-500">
            Download everything Pulse has stored for your account — watchlists, digests, and chat history — as a
            JSON file.
          </p>
          <button
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:border-blue-500 hover:text-blue-600 dark:border-slate-700"
          >
            {exportMutation.isPending ? 'Preparing…' : 'Export my data'}
          </button>
        </section>

        <section className="rounded-xl border border-rose-200 p-4 dark:border-rose-900">
          <h2 className="mb-2 text-sm font-semibold text-rose-700 dark:text-rose-400">Danger zone</h2>
          <p className="mb-3 text-xs text-slate-500">
            Deleting your account deactivates it immediately and clears your chat history. This can't be undone from
            the app.
          </p>
          {!confirmOpen ? (
            <button
              onClick={() => setConfirmOpen(true)}
              className="rounded-lg border border-rose-300 px-3 py-1.5 text-sm text-rose-700 hover:bg-rose-50 dark:border-rose-800 dark:text-rose-400 dark:hover:bg-rose-950"
            >
              Delete my account
            </button>
          ) : (
            <div className="space-y-2">
              <input
                type="password"
                placeholder="Confirm your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-rose-500 dark:border-slate-700"
              />
              {deleteError && <p className="text-xs text-rose-600">{deleteError}</p>}
              <div className="flex gap-2">
                <button
                  onClick={() => deleteMutation.mutate(password)}
                  disabled={!password || deleteMutation.isPending}
                  className="rounded-lg bg-rose-600 px-3 py-1.5 text-sm text-white hover:bg-rose-700 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? 'Deleting…' : 'Permanently delete'}
                </button>
                <button
                  onClick={() => {
                    setConfirmOpen(false)
                    setPassword('')
                    setDeleteError(null)
                  }}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>

        <p className="text-center text-xs text-slate-400">
          <Link to="/privacy" className="hover:underline">
            Privacy Policy
          </Link>{' '}
          ·{' '}
          <Link to="/terms" className="hover:underline">
            Terms of Service
          </Link>
        </p>
      </div>
    </div>
  )
}
