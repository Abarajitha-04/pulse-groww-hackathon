import { useQuery } from '@tanstack/react-query'
import { fetchHistory } from '../api/watchlists'

/**
 * Deliberately a hand-rolled inline SVG polyline, not the lightweight-charts
 * library — a 30-point sparkline in a table cell doesn't need a full
 * charting engine's pan/zoom/crosshair machinery, and a plain SVG is
 * lighter, has zero layout-sizing surprises inside a table row, and is
 * trivial to theme. lightweight-charts is the right tool for a full
 * candlestick chart, which is a reasonable "next" addition, not a
 * reasonable sparkline implementation.
 */
export function Sparkline({ symbol }: { symbol: string }) {
  const { data: points, isLoading } = useQuery({
    queryKey: ['history', symbol],
    queryFn: () => fetchHistory(symbol, 30),
    staleTime: 30_000,
  })

  if (isLoading || !points || points.length < 2) {
    return <div className="h-8 w-24 rounded bg-slate-100 dark:bg-slate-800" />
  }

  const prices = points.map((p) => p.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const width = 96
  const height = 32
  const stepX = width / (prices.length - 1)

  const coords = prices.map((p, i) => {
    const x = i * stepX
    const y = height - ((p - min) / range) * height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const up = prices[prices.length - 1] >= prices[0]
  const color = up ? '#10b981' : '#f43f5e'

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
