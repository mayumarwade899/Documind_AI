import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  FlaskConical, CheckCircle, XCircle, BookOpen,
  Plus, ChevronDown, ChevronUp, Info, Clock,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

import { api } from '../services/api.js'
import { runEvaluation as runEvalAPI } from '../services/evaluationService.js'
import { Badge, Button, Card, Skeleton, EmptyState, Progress } from '../components/ui/index.jsx'
import { formatPercent, formatLatency } from '../utils/format.js'
import { cn } from '../utils/cn.js'
import { useUIStore } from '../store/uiStore.js'

const THRESHOLDS = {
  faithfulness: 0.7,
  context_relevance: 0.7,
  answer_correctness: 0.6,
}

function ScoreGauge({ score, threshold, label }) {
  const passed = (score ?? 0) >= threshold
  const pct = Math.round((score ?? 0) * 100)
  const r = 30
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ

  const ringColor = passed ? 'stroke-emerald-500' : 'stroke-red-400'
  const trackColor = 'stroke-surface-100 dark:stroke-surface-700'
  const textColor = passed
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-500 dark:text-red-400'

  return (
    <div className="flex flex-col items-center gap-2 p-5 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
          <circle cx="40" cy="40" r={r} fill="none" className={trackColor} strokeWidth="7" />
          <circle
            cx="40" cy="40" r={r} fill="none"
            className={ringColor} strokeWidth="7"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('text-xl font-bold tabular-nums', textColor)}>{pct}</span>
          <span className="text-[9px] text-surface-400 leading-none">/100</span>
        </div>
      </div>

      <div className="text-center">
        <p className="text-xs font-semibold text-surface-700 dark:text-surface-300 capitalize leading-tight">
          {label.replace(/_/g, ' ')}
        </p>
        <div className="flex items-center gap-1 justify-center mt-1.5">
          {passed
            ? <CheckCircle size={11} className="text-emerald-500" />
            : <XCircle size={11} className="text-red-400" />}
          <span className={cn('text-[10px] font-medium', textColor)}>
            {passed ? 'Pass' : 'Fail'} · min {Math.round(threshold * 100)}
          </span>
        </div>
      </div>
    </div>
  )
}



export default function EvaluationPage() {
  const [tab, setTab] = useState('results')
  const { isEvaluating, setEvaluating } = useUIStore()

  const { data: report, isLoading: reportLoading, refetch: refetchReport } = useQuery({
    queryKey: ['eval-report'],
    queryFn: () => api.get('/evaluation/latest').catch(() => null),
    retry: 0,
  })

  const { data: historyReports, isLoading: historyLoading, refetch: refetchHistory } = useQuery({
    queryKey: ['eval-history'],
    queryFn: () => api.get('/evaluation/history').catch(() => []),
    retry: 0,
  })

  useEffect(() => {
    async function syncStatus() {
      try {
        const status = await api.get('/evaluation/status')
        if (status.is_running) {
          setEvaluating(true)
        }
      } catch (err) {
        console.error('Failed to sync evaluation status', err)
      }
    }
    syncStatus()
  }, [setEvaluating])

  const { data: statusData } = useQuery({
    queryKey: ['eval-status'],
    queryFn: () => api.get('/evaluation/status'),
    enabled: isEvaluating,
    refetchInterval: isEvaluating ? 3000 : false,
  })

  useEffect(() => {
    if (isEvaluating && statusData && statusData.is_running === false) {
      setEvaluating(false)

      refetchReport()
      refetchHistory()

      if (statusData.error) {
        toast.error(`Evaluation failed: ${statusData.error}`)
      } else {
        toast.success('Evaluation complete! Metrics updated.')
      }
    }
  }, [statusData, isEvaluating, setEvaluating, refetchReport, refetchHistory])

  async function handleRunEvaluation() {
    setEvaluating(true)
    setTab('results')
    try {
      await runEvalAPI()
      toast.success('Evaluation started in background', { id: 'eval-start' })
    } catch (err) {
      setEvaluating(false)
      const msg = err?.detail || err?.message || 'Failed to start evaluation'
      toast.error(msg)
    }
  }

  const displayReport = report ?? {
    run_id: 'no-run-yet',
    timestamp: null,
    dataset_size: '-',
    overall_passed: null,
    avg_score: null,
    metrics: {
      faithfulness: { score: null, threshold: THRESHOLDS.faithfulness, passed: null },
      context_relevance: { score: null, threshold: THRESHOLDS.context_relevance, passed: null },
      answer_correctness: { score: null, threshold: THRESHOLDS.answer_correctness, passed: null },
    },
    evaluation_latency_ms: null,
  }

  const hasRealReport = !!report

  const TABS = [
    { id: 'results', label: 'Evaluation results', icon: <FlaskConical size={12} /> },
    { id: 'history', label: 'History', icon: <Clock size={12} /> },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between h-14 px-6 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
        <div>
          <h1 className="text-base font-semibold text-surface-900 dark:text-white">TruLens Evaluation</h1>
          <p className="text-xs text-surface-400">
            Reference-free pipeline quality gate against historical queries
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          disabled={isEvaluating}
          onClick={handleRunEvaluation}
        >
          {isEvaluating ? (
            <>
              <div className="w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
              Running…
            </>
          ) : (
            <>
              <FlaskConical size={14} />
              Run evaluation
            </>
          )}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        <div className="flex gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-lg w-fit">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                tab === t.id
                  ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
                  : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'results' && (
          <div className="space-y-5">
            {!hasRealReport && (
              <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900">
                <Info size={16} className="text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                    No evaluation run yet
                  </p>
                  <p className="text-xs text-amber-600 dark:text-amber-500 mt-0.5">
                    Click <strong>Run evaluation</strong> above to generate TruLens quality scores for your RAG pipeline against recent historical user queries.
                  </p>
                </div>
              </div>
            )}

            {hasRealReport && (
              <div className={cn(
                'flex items-center gap-3 p-4 rounded-xl border',
                displayReport.overall_passed
                  ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900'
                  : 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900'
              )}>
                {displayReport.overall_passed
                  ? <CheckCircle size={20} className="text-emerald-500 shrink-0" />
                  : <XCircle size={20} className="text-red-400 shrink-0" />}
                <div>
                  <p className={cn(
                    'font-semibold',
                    displayReport.overall_passed
                      ? 'text-emerald-700 dark:text-emerald-400'
                      : 'text-red-600 dark:text-red-400'
                  )}>
                    {displayReport.overall_passed
                      ? 'All metrics pass — deployment approved'
                      : 'Quality gate failed — fix before deploying'}
                  </p>
                  <p className="text-xs text-surface-400 mt-0.5">
                    Run {displayReport.run_id}
                    {displayReport.timestamp && ` · ${new Date(displayReport.timestamp).toLocaleString()}`}
                    {displayReport.dataset_size > 0 && ` · ${displayReport.dataset_size} QA pairs`}
                    {displayReport.avg_score != null && ` · avg score ${formatPercent(displayReport.avg_score)}`}
                    {displayReport.evaluation_latency_ms != null && ` · ${formatLatency(displayReport.evaluation_latency_ms)}`}
                  </p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-3 gap-4">
              {Object.entries(displayReport.metrics).map(([key, m]) => (
                <ScoreGauge
                  key={key}
                  score={hasRealReport ? m.score : null}
                  threshold={m.threshold ?? THRESHOLDS[key]}
                  label={key}
                />
              ))}
            </div>

            <Card className="p-4">
              <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-3">
                Configured quality thresholds
              </h3>
              <div className="space-y-2.5">
                {Object.entries(THRESHOLDS).map(([key, val]) => (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-xs text-surface-500 capitalize w-40 shrink-0">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <div className="flex-1">
                      <Progress value={val * 100} variant="brand" />
                    </div>
                    <span className="text-xs font-mono font-semibold text-surface-600 dark:text-surface-400 w-8 text-right">
                      {val}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}


        {tab === 'history' && (
          <div className="space-y-4">
            {historyLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-10 bg-white dark:bg-surface-850 rounded-lg border border-surface-200 dark:border-surface-700 skeleton" />
                ))}
              </div>
            ) : !historyReports?.length ? (
              <EmptyState title="No history" description="Run an evaluation to see past results here." icon={<Clock className="w-10 h-10 mx-auto text-surface-300" />} />
            ) : (
              <Card className="overflow-hidden p-0">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-50 dark:bg-surface-800/50 border-b border-surface-200 dark:border-surface-700">
                    <tr>
                      <th className="px-4 py-3 font-semibold text-surface-500">Run ID</th>
                      <th className="px-4 py-3 font-semibold text-surface-500">Date</th>
                      <th className="px-4 py-3 font-semibold text-surface-500">Status</th>
                      <th className="px-4 py-3 font-semibold text-surface-500 text-right">Avg Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
                    {historyReports.map(r => (
                      <tr key={r.run_id} className="hover:bg-surface-50 dark:hover:bg-surface-800/50">
                        <td className="px-4 py-3 font-mono text-[10px] text-surface-500">{r.run_id.split('-').shift() ?? r.run_id}</td>
                        <td className="px-4 py-3 text-surface-700 dark:text-surface-300">
                          {new Date(r.timestamp).toLocaleString(undefined, {
                            dateStyle: 'short', timeStyle: 'short'
                          })}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={r.overall_passed ? 'success' : 'danger'} size="xs">
                            {r.overall_passed ? 'Passed' : 'Failed'}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold text-surface-700 dark:text-surface-300">
                          {formatPercent(r.avg_score)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
