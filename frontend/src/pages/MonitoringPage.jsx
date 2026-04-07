import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, LineChart, Line
} from 'recharts'
import { Zap, DollarSign, Hash, CheckCircle, TrendingUp, AlertCircle, Clock } from 'lucide-react'

import { getMetrics, getDailyMetrics } from '../services/metricsService.js'
import { getFeedbackSummary, getNegativeFeedback } from '../services/queryService.js'
import { MetricCard } from '../components/shared/index.jsx'
import { Badge, Skeleton, Tabs, Card } from '../components/ui/index.jsx'
import { formatCost, formatLatency, formatTokens, formatPercent, timeAgo } from '../utils/format.js'
import { cn } from '../utils/cn.js'
import { useUIStore } from '../store/uiStore.js'

function ChartTooltipContent({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white dark:bg-surface-850 border border-surface-200 dark:border-surface-700 rounded-lg px-3 py-2 shadow-card text-xs">
      <p className="font-medium text-surface-700 dark:text-surface-300 mb-1">{label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  )
}

export default function MonitoringPage() {
  const [days, setDays] = useState(7)
  const [tab, setTab]   = useState('overview')
  const { theme } = useUIStore()

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics', days],
    queryFn: () => getMetrics(days),
    refetchInterval: 30_000,
  })

  const { data: daily } = useQuery({
    queryKey: ['daily-metrics', days],
    queryFn: () => getDailyMetrics(days),
  })

  const { data: feedback } = useQuery({
    queryKey: ['feedback-summary', days],
    queryFn: () => getFeedbackSummary(days),
  })

  const { data: negativeFeedback } = useQuery({
    queryKey: ['negative-feedback', days],
    queryFn: () => getNegativeFeedback(days),
  })

  const chartColor = theme === 'dark' ? '#a78bfa' : '#7c4dff'
  const gridColor  = theme === 'dark' ? '#2a2a32' : '#f1f1f3'
  const axisColor  = theme === 'dark' ? '#52525e' : '#d0d0d6'

  const dailyData = (daily?.days ?? []).slice().reverse().map(d => ({
    date: d.date?.slice(5),
    requests: d.total_requests,
    latency: Math.round(d.avg_latency_ms ?? 0),
    cost: parseFloat((d.total_cost_usd ?? 0).toFixed(5)),
    success: d.successful,
    failed: d.failed,
  }))

  const tabs = [
    { id: 'overview',  label: 'Overview'  },
    { id: 'latency',   label: 'Latency'   },
    { id: 'cost',      label: 'Cost'      },
    { id: 'feedback',  label: 'Feedback'  },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between h-14 px-6 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
        <div>
          <h1 className="text-base font-semibold text-surface-900 dark:text-white">Monitoring</h1>
          <p className="text-xs text-surface-400">System health and performance metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-400">Period:</span>
          {[7, 14, 30].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                'px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                days === d
                  ? 'bg-brand-100 dark:bg-brand-950 text-brand-700 dark:text-brand-300'
                  : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800'
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
          ) : metrics ? (
            <>
              <MetricCard icon={<Hash size={16} />}         label="Total requests" value={metrics.total_requests?.toLocaleString() ?? '—'} sub={`${metrics.successful} successful · ${metrics.failed} failed`} color="brand" />
              <MetricCard icon={<Zap size={16} />}          label="p95 latency"    value={formatLatency(metrics.latency?.p95_ms)} sub={`avg ${formatLatency(metrics.latency?.avg_ms)}`} color="amber" />
              <MetricCard icon={<DollarSign size={16} />}   label="Total cost"     value={formatCost(metrics.total_cost_usd)} sub={`~${formatCost(metrics.avg_cost_usd)} / request`} color="emerald" />
              <MetricCard icon={<CheckCircle size={16} />}  label="Success rate"   value={formatPercent(metrics.success_rate)} sub={`${metrics.total_requests} total queries`} color="sky" />
            </>
          ) : null}
        </div>

        {/* Tabs */}
        <Tabs tabs={tabs} active={tab} onChange={setTab} />

        {/* Charts */}
        {tab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4">Requests per day</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={dailyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: axisColor }} />
                  <YAxis tick={{ fontSize: 11, fill: axisColor }} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="success" name="Success" fill={chartColor} radius={[3, 3, 0, 0]} />
                  <Bar dataKey="failed"  name="Failed"  fill="#f87171" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4">Avg latency (ms)</h3>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={dailyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={chartColor} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: axisColor }} />
                  <YAxis tick={{ fontSize: 11, fill: axisColor }} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Area type="monotone" dataKey="latency" name="Latency ms" stroke={chartColor} strokeWidth={2} fill="url(#latGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
          </div>
        )}

        {tab === 'latency' && metrics && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4">Latency percentiles</h3>
              <div className="space-y-3">
                {[
                  { label: 'p50', value: metrics.latency?.p50_ms, color: 'bg-emerald-400' },
                  { label: 'p95', value: metrics.latency?.p95_ms, color: 'bg-amber-400' },
                  { label: 'p99', value: metrics.latency?.p99_ms, color: 'bg-red-400' },
                ].map(p => {
                  const max = (metrics.latency?.p99_ms || 1)
                  return (
                    <div key={p.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-mono text-surface-500">{p.label}</span>
                        <span className="font-semibold text-surface-700 dark:text-surface-300">{formatLatency(p.value)}</span>
                      </div>
                      <div className="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
                        <div className={cn('h-full rounded-full transition-all', p.color)} style={{ width: `${(p.value / max) * 100}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
              <div className="mt-4 pt-4 border-t border-surface-100 dark:border-surface-700 grid grid-cols-2 gap-3 text-xs">
                <div><span className="text-surface-400">Min</span><p className="font-semibold mt-0.5">{formatLatency(metrics.latency?.min_ms)}</p></div>
                <div><span className="text-surface-400">Max</span><p className="font-semibold mt-0.5">{formatLatency(metrics.latency?.max_ms)}</p></div>
                <div><span className="text-surface-400">Avg</span><p className="font-semibold mt-0.5">{formatLatency(metrics.latency?.avg_ms)}</p></div>
                <div><span className="text-surface-400">Samples</span><p className="font-semibold mt-0.5">{metrics.latency?.samples}</p></div>
              </div>
            </Card>

            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4">Daily latency trend</h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={dailyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: axisColor }} />
                  <YAxis tick={{ fontSize: 11, fill: axisColor }} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Line type="monotone" dataKey="latency" name="Avg ms" stroke={chartColor} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>
        )}

        {tab === 'cost' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4">Cost per day</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={dailyData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
                  <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: axisColor }} />
                  <YAxis tick={{ fontSize: 11, fill: axisColor }} tickFormatter={v => `$${v}`} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="cost" name="Cost $" fill="#10b981" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card className="p-4 space-y-3">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">Cost summary</h3>
              {[
                { label: 'Total cost',    value: formatCost(metrics?.total_cost_usd) },
                { label: 'Avg per req',   value: formatCost(metrics?.avg_cost_usd) },
                { label: 'Total tokens',  value: formatTokens(metrics?.total_tokens) },
                { label: 'Avg tokens',    value: formatTokens(metrics?.avg_tokens) },
                { label: 'Avg support',   value: formatPercent(metrics?.avg_support_ratio) },
              ].map(r => (
                <div key={r.label} className="flex justify-between py-2 border-b border-surface-100 dark:border-surface-800 last:border-0 text-sm">
                  <span className="text-surface-500">{r.label}</span>
                  <span className="font-semibold font-mono text-surface-800 dark:text-surface-200">{r.value}</span>
                </div>
              ))}
            </Card>
          </div>
        )}

        {tab === 'feedback' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-4">Feedback summary</h3>
              {feedback ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3 text-center">
                    {[
                      { label: 'Positive', value: feedback.positive, color: 'text-emerald-600 dark:text-emerald-400' },
                      { label: 'Neutral',  value: feedback.neutral,  color: 'text-surface-500' },
                      { label: 'Negative', value: feedback.negative, color: 'text-red-500' },
                    ].map(f => (
                      <div key={f.label}>
                        <p className={cn('text-2xl font-semibold', f.color)}>{f.value}</p>
                        <p className="text-xs text-surface-400 mt-0.5">{f.label}</p>
                      </div>
                    ))}
                  </div>
                  <div className="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden flex">
                    <div className="h-full bg-emerald-400" style={{ width: `${feedback.positive_rate * 100}%` }} />
                    <div className="h-full bg-red-400"     style={{ width: `${feedback.negative_rate * 100}%` }} />
                  </div>
                  <p className="text-xs text-surface-400 text-center">
                    {formatPercent(feedback.positive_rate)} positive · avg rating {feedback.avg_rating?.toFixed(2)}
                  </p>
                </div>
              ) : <Skeleton className="h-32" />}
            </Card>

            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-3">Negative feedback</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {negativeFeedback?.feedback?.length ? (
                  negativeFeedback.feedback.map((f) => (
                    <div key={f.feedback_id} className="p-2.5 rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/20">
                      <p className="text-xs font-medium text-surface-700 dark:text-surface-300 truncate">{f.query}</p>
                      {f.comment && <p className="text-xs text-red-600 dark:text-red-400 mt-1 italic">"{f.comment}"</p>}
                      <p className="text-[10px] text-surface-400 mt-1">{timeAgo(f.date)}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-surface-400 text-center py-6">No negative feedback 🎉</p>
                )}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
