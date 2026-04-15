import { cn } from '../../utils/cn.js'
import { formatCost, formatTokens, formatLatency } from '../../utils/format.js'
import { CheckCircle, AlertCircle, Clock, DollarSign, Hash } from 'lucide-react'

export function ConfidenceBar({ ratio, hasCitations, className }) {
  const pct = Math.round((ratio ?? 0) * 100)
  const color =
    pct >= 80 ? 'bg-emerald-500' :
      pct >= 50 ? 'bg-amber-400' :
        'bg-red-400'
  const textColor =
    pct >= 80 ? 'text-emerald-600 dark:text-emerald-400' :
      pct >= 50 ? 'text-amber-600 dark:text-amber-400' :
        'text-red-600 dark:text-red-400'
  return (
    <div className={cn('mt-3 pt-3 border-t border-surface-100 dark:border-surface-700/60', className)}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-medium text-surface-400 uppercase tracking-wide">Answer confidence</span>
        <div className="flex items-center gap-1">
          {hasCitations
            ? <CheckCircle size={11} className="text-emerald-500" />
            : <AlertCircle size={11} className="text-amber-500" />}
          <span className={cn('text-xs font-semibold tabular-nums', textColor)}>{pct}%</span>
        </div>
      </div>
      <div className="h-1 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all duration-700', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function InlineMeta({ metrics, className }) {
  if (!metrics) return null
  return (
    <div className={cn('flex items-center gap-3 flex-wrap', className)}>
      <MetaPill icon={<Clock size={10} />} value={formatLatency(metrics.total_latency_ms)} />
      <MetaPill icon={<Hash size={10} />} value={`${formatTokens(metrics.total_tokens)} tok`} />
      <MetaPill icon={<DollarSign size={10} />} value={formatCost(metrics.cost_usd)} />
      <span className="text-surface-300 dark:text-surface-600">·</span>
      <span className="text-[10px] text-surface-400">{metrics.num_chunks_used} chunks</span>
      {metrics.num_queries_used > 1 && (
        <span className="text-[10px] text-surface-400">{metrics.num_queries_used} queries</span>
      )}
    </div>
  )
}

function MetaPill({ icon, value }) {
  return (
    <span className="flex items-center gap-1 text-[10px] font-mono text-surface-400">
      {icon}{value}
    </span>
  )
}

export function MetricCard({ icon, label, value, sub, trend, color = 'brand' }) {
  const colors = {
    brand: 'bg-brand-50 dark:bg-brand-950/50 text-brand-600 dark:text-brand-400',
    amber: 'bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400',
    emerald: 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400',
    sky: 'bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400',
    red: 'bg-red-50 dark:bg-red-950/50 text-red-600 dark:text-red-400',
  }
  return (
    <div className="bg-white dark:bg-surface-850 rounded-xl p-4 border border-surface-200 dark:border-surface-700 shadow-card">
      <div className={cn('inline-flex p-2 rounded-lg mb-3', colors[color])}>
        {icon}
      </div>
      <p className="text-2xl font-semibold text-surface-900 dark:text-white tabular-nums">{value}</p>
      <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">{label}</p>
      {sub && <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">{sub}</p>}
      {trend != null && (
        <div className={cn('mt-2 text-xs font-medium', trend >= 0 ? 'text-emerald-600' : 'text-red-500')}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
        </div>
      )}
    </div>
  )
}
