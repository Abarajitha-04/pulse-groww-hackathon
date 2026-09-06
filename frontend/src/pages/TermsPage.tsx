import { Link } from 'react-router-dom'

export function TermsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
      <Link to="/" className="mb-6 inline-block text-xs text-slate-400 hover:text-blue-600">
        ← Back
      </Link>
      <h1 className="mb-1 text-xl font-bold text-slate-900 dark:text-white">Terms of Service</h1>
      <p className="mb-6 text-xs italic text-amber-600 dark:text-amber-400">
        Draft template — not reviewed by a lawyer. Replace this notice and have counsel review these terms before
        relying on them for a real launch.
      </p>

      <div className="space-y-4">
        <p>By creating an account, you agree to these terms.</p>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">1. Not financial advice</h2>
          <p>
            Pulse shows you price data and describes changes to stocks on your watchlist. Nothing in the app —
            including the AI-generated digests and chat responses — is investment advice, a recommendation to buy or
            sell any security, or a prediction of future performance. Decisions about your investments are yours
            alone; consult a licensed financial advisor for guidance specific to your situation.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">2. Market data</h2>
          <p>
            Price data may come from free, unofficial, or delayed sources depending on configuration, and can be
            stale, incomplete, or wrong. Do not use Pulse as your sole source of truth for a time-sensitive trading
            decision.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">3. AI features</h2>
          <p>
            The digest and chat assistant use a third-party AI model (Groq) to phrase already-computed numbers in
            plain language. The AI is instructed not to invent figures and not to give investment advice, but AI
            output can still be wrong — verify anything important against the underlying numbers shown in the app.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">4. Your account</h2>
          <p>
            You're responsible for keeping your password secure. You can export your data or delete your account at
            any time from Settings.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">5. Service availability</h2>
          <p>
            Pulse is provided "as is," without warranty of any kind. We may change or discontinue features, and
            uptime is not guaranteed.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">6. Changes</h2>
          <p>We may update these terms; continued use after a change means you accept the update.</p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">Contact</h2>
          <p>Questions about these terms: [add your support email here].</p>
        </section>
      </div>
    </div>
  )
}
