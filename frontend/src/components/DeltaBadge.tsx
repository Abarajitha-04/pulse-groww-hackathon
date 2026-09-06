import type { Delta } from '../api/types'

/**
 * The single most important visual element in the product: it must make
 * "significant vs. not" instantly legible, and explain itself on hover
 * via the `reason` field the diff engine already computed — no separate
 * tooltip logic needed, we just surface data that already exists.
 */
export function DeltaBadge({ delta }: { delta: Delta }) {
  if (delta.current_price === null) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-200 px-2.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        awaiting data
      </span>
    )
  }

  if (delta.last_seen_price === null) {
    return (
      <span
        title={delta.reason}
        className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300"
      >
        new
      </span>
    )
  }

  const pct = delta.price_change_pct ?? 0
  const up = pct >= 0

  if (!delta.significant) {
    return (
      <span
        title={delta.reason}
        className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400"
      >
        {(pct * 100).toFixed(2)}% · quiet
      </span>
    )
  }

  return (
    <span
      title={delta.reason}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold animate-pulse ${
        up
          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
          : 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
      }`}
    >
      {up ? '▲' : '▼'} {(pct * 100).toFixed(2)}%
      {delta.price_z_score !== null && (
        <span className="opacity-70">· z={delta.price_z_score.toFixed(1)}</span>
      )}
    </span>
  )
}
