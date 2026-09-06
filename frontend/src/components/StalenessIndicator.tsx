/**
 * Staleness is a first-class UI state, not a hidden bug (blueprint §7/§8).
 * If the ingestion pipeline degrades, the user sees this instead of a
 * confidently wrong number.
 */
export function StalenessIndicator({ stale, source }: { stale?: boolean; source?: string }) {
  if (!stale) return null
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
      ⚠ delayed{source ? ` · ${source}` : ''}
    </span>
  )
}
