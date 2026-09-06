import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login, signup } from '../api/auth'
import { useAuthStore } from '../store/authStore'

export function AuthPage() {
  const [mode, setMode] = useState<'login' | 'signup'>('signup')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const setTokens = useAuthStore((s) => s.setTokens)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const tokens = mode === 'signup' ? await signup(email, password) : await login(email, password)
      setTokens(tokens)
      navigate('/')
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h1 className="mb-1 text-2xl font-bold">Pulse</h1>
        <p className="mb-6 text-sm text-slate-500">A watchlist that tells you what you missed.</p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700"
          />
          <input
            type="password"
            required
            minLength={6}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700"
          />
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {mode === 'signup' ? 'Create account' : 'Log in'}
          </button>
        </form>

        <button
          onClick={() => setMode(mode === 'signup' ? 'login' : 'signup')}
          className="mt-4 text-xs text-slate-500 hover:underline"
        >
          {mode === 'signup' ? 'Already have an account? Log in' : "Don't have an account? Sign up"}
        </button>

        {mode === 'signup' && (
          <p className="mt-6 text-center text-[11px] text-slate-400">
            By creating an account you agree to our{' '}
            <Link to="/terms" className="hover:underline">
              Terms
            </Link>{' '}
            and{' '}
            <Link to="/privacy" className="hover:underline">
              Privacy Policy
            </Link>
            .
          </p>
        )}
      </div>
    </div>
  )
}
