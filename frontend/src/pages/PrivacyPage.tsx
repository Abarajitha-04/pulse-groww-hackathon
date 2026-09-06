import { Link } from 'react-router-dom'

export function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
      <Link to="/" className="mb-6 inline-block text-xs text-slate-400 hover:text-blue-600">
        ← Back
      </Link>
      <h1 className="mb-1 text-xl font-bold text-slate-900 dark:text-white">Privacy Policy</h1>
      <p className="mb-6 text-xs italic text-amber-600 dark:text-amber-400">
        Draft template — not reviewed by a lawyer, and not a substitute for a jurisdiction-specific privacy notice
        (GDPR/CCPA/DPDP obligations vary). Have counsel review before a real launch.
      </p>

      <div className="space-y-4">
        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">What we collect</h2>
          <p>
            Your email address and password (stored as a one-way hash, never in plain text), the stock symbols you
            add to watchlists, and your chat messages with the assistant. We do not collect payment information,
            government ID, or biometric data.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">How we use it</h2>
          <p>
            To run the product: showing your watchlists, computing what's changed, generating digests, answering
            your chat questions, and — if you opt in under Settings — emailing you when a watched stock moves
            significantly.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">Third parties</h2>
          <p>
            Your watchlist's price-change data (never your email or raw chat text beyond what's needed to answer
            you) may be sent to Groq, our AI provider, to generate digests and chat responses. See Groq's own privacy
            policy for how they handle that data. We don't sell your data to advertisers or data brokers.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">Your controls</h2>
          <p>
            From Settings, you can export a copy of everything we've stored for your account, or delete your account
            — which deactivates it immediately, clears your chat history, and revokes all active sessions.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">Retention</h2>
          <p>
            We keep account data while your account is active. After deletion, your email is removed and the
            account deactivated immediately; some records (like historical price snapshots, which aren't personally
            identifying) may be retained for the product to keep working for other users.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">Security</h2>
          <p>
            Passwords are hashed, not stored in plain text. Sessions use short-lived access tokens plus a revocable
            refresh token, so logging out (or resetting your password) actually invalidates prior sessions rather
            than just hiding the button.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold text-slate-900 dark:text-white">Contact</h2>
          <p>Questions about this policy or your data: [add your support email here].</p>
        </section>
      </div>
    </div>
  )
}
