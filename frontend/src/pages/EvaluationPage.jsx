import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  FlaskConical, CheckCircle, XCircle, BookOpen,
  Plus, ChevronDown, ChevronUp, Info,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

import { api } from '../services/api.js'
import { runEvaluation as runEvalAPI } from '../services/evaluationService.js'
import { Badge, Button, Card, Skeleton, EmptyState, Progress } from '../components/ui/index.jsx'
import { formatPercent, formatLatency } from '../utils/format.js'
import { cn } from '../utils/cn.js'

// Quality thresholds — must match your .env / config/settings.py
const THRESHOLDS = {
  faithfulness:       0.7,
  context_relevance:  0.7,
  answer_correctness: 0.6,
}

// ─── ScoreGauge ───
function ScoreGauge({ score, threshold, label }) {
  const passed = (score ?? 0) >= threshold
  const pct    = Math.round((score ?? 0) * 100)
  const r      = 30
  const circ   = 2 * Math.PI * r
  const dash   = (pct / 100) * circ

  const ringColor  = passed ? 'stroke-emerald-500' : 'stroke-red-400'
  const trackColor = 'stroke-surface-100 dark:stroke-surface-700'
  const textColor  = passed
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-500 dark:text-red-400'

  return (
    <div className="flex flex-col items-center gap-2 p-5 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700">
      {/* Circular ring */}
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

      {/* Label + status */}
      <div className="text-center">
        <p className="text-xs font-semibold text-surface-700 dark:text-surface-300 capitalize leading-tight">
          {label.replace(/_/g, ' ')}
        </p>
        <div className="flex items-center gap-1 justify-center mt-1.5">
          {passed
            ? <CheckCircle size={11} className="text-emerald-500" />
            : <XCircle    size={11} className="text-red-400" />}
          <span className={cn('text-[10px] font-medium', textColor)}>
            {passed ? 'Pass' : 'Fail'} · min {Math.round(threshold * 100)}
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── GoldenPairRow ───
function GoldenPairRow({ pair, index }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border-b border-surface-100 dark:border-surface-800 last:border-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-3 px-4 py-3 hover:bg-surface-50 dark:hover:bg-surface-800/40 text-left transition-colors"
      >
        {/* Index bubble */}
        <span className="shrink-0 w-6 h-6 rounded-full bg-brand-100 dark:bg-brand-950 text-brand-700 dark:text-brand-300 text-[10px] font-bold flex items-center justify-center mt-0.5">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">
            {pair.question}
          </p>
          {!expanded && (
            <p className="text-xs text-surface-400 mt-0.5 truncate">
              {pair.ground_truth}
            </p>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {pair.source_files?.slice(0, 2).map((f) => (
            <Badge key={f} variant="default" size="xs">
              {f}
            </Badge>
          ))}
          {pair.metadata?.manually_created && (
            <Badge variant="brand" size="xs">manual</Badge>
          )}
          {expanded
            ? <ChevronUp size={13} className="text-surface-400" />
            : <ChevronDown size={13} className="text-surface-400" />}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 ml-9 space-y-3">
              {/* Ground truth */}
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-1">
                  Ground truth
                </p>
                <p className="text-xs text-surface-600 dark:text-surface-400 leading-relaxed">
                  {pair.ground_truth}
                </p>
              </div>

              {/* Contexts */}
              {pair.contexts?.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-1">
                    Contexts ({pair.contexts.length})
                  </p>
                  {pair.contexts.map((c, i) => (
                    <p
                      key={i}
                      className="text-xs text-surface-500 dark:text-surface-500 leading-relaxed mb-1.5 pl-2.5 border-l-2 border-surface-200 dark:border-surface-700"
                    >
                      {c.length > 240 ? c.slice(0, 240) + '…' : c}
                    </p>
                  ))}
                </div>
              )}

              {/* Source files */}
              {pair.source_files?.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {pair.source_files.map((f) => (
                    <Badge key={f} variant="outline" size="xs">{f}</Badge>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── EvaluationPage ───
export default function EvaluationPage() {
  const [tab, setTab] = useState('dataset')
  const [isRunning, setIsRunning] = useState(false)

  // Golden dataset
  const {
    data: goldenData,
    isLoading: datasetLoading,
    error: datasetError,
  } = useQuery({
    queryKey: ['golden-dataset'],
    queryFn: () => api.get('/evaluation/dataset'),
    retry: 1,
  })

  // Latest eval report
  const { data: report, isLoading: reportLoading, refetch: refetchReport } = useQuery({
    queryKey: ['eval-report'],
    queryFn: () => api.get('/evaluation/latest').catch(() => null),
    retry: 0,
  })

  async function handleRunEvaluation() {
    setIsRunning(true)
    setTab('results')
    try {
      await runEvalAPI()
      await refetchReport()
      toast.success('Evaluation complete!')
    } catch (err) {
      const msg = err?.detail || err?.message || 'Evaluation failed'
      toast.error(msg)
    } finally {
      setIsRunning(false)
    }
  }

  const pairs = goldenData?.pairs ?? []

  // If no real report, show a demo placeholder so the UI doesn't look broken
  const displayReport = report ?? {
    run_id: 'no-run-yet',
    timestamp: null,
    dataset_size: pairs.length,
    overall_passed: null,
    avg_score: null,
    metrics: {
      faithfulness:       { score: null, threshold: THRESHOLDS.faithfulness,       passed: null },
      context_relevance:  { score: null, threshold: THRESHOLDS.context_relevance,  passed: null },
      answer_correctness: { score: null, threshold: THRESHOLDS.answer_correctness, passed: null },
    },
    evaluation_latency_ms: null,
  }

  const hasRealReport = !!report

  const TABS = [
    { id: 'dataset', label: 'Golden dataset', icon: <BookOpen size={12} /> },
    { id: 'results', label: 'RAGAS results',  icon: <FlaskConical size={12} /> },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between h-14 px-6 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
        <div>
          <h1 className="text-base font-semibold text-surface-900 dark:text-white">Evaluation</h1>
          <p className="text-xs text-surface-400">
            RAGAS quality gate · {pairs.length} golden QA pairs
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          disabled={isRunning}
          onClick={handleRunEvaluation}
        >
          {isRunning ? (
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
        {/* Tab bar */}
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

        {/* RAGAS Results tab */}
        {tab === 'results' && (
          <div className="space-y-5">
            {/* No-run banner */}
            {!hasRealReport && (
              <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900">
                <Info size={16} className="text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                    No evaluation run yet
                  </p>
                  <p className="text-xs text-amber-600 dark:text-amber-500 mt-0.5">
                    Click <strong>Run evaluation</strong> above to generate RAGAS quality scores for your RAG pipeline.
                  </p>
                </div>
              </div>
            )}

            {/* Overall pass/fail */}
            {hasRealReport && (
              <div className={cn(
                'flex items-center gap-3 p-4 rounded-xl border',
                displayReport.overall_passed
                  ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900'
                  : 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900'
              )}>
                {displayReport.overall_passed
                  ? <CheckCircle size={20} className="text-emerald-500 shrink-0" />
                  : <XCircle    size={20} className="text-red-400 shrink-0" />}
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

            {/* Score gauges */}
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

            {/* Threshold reference */}
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
              <p className="text-[10px] text-surface-400 mt-3 font-mono">
                Override via env: MIN_FAITHFULNESS_SCORE · MIN_CONTEXT_RELEVANCE_SCORE · MIN_ANSWER_CORRECTNESS_SCORE
              </p>
            </Card>
          </div>
        )}

        {/* Dataset tab */}
        {tab === 'dataset' && (
          <div className="space-y-4">
            {/* Header row */}
            <div className="flex items-center justify-between">
              <p className="text-sm text-surface-500 dark:text-surface-400">
                {datasetLoading
                  ? 'Loading…'
                  : datasetError
                  ? 'Could not load dataset'
                  : `${pairs.length} QA pair${pairs.length !== 1 ? 's' : ''}`}
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  toast('Run: python scripts/generate_golden.py --auto-approve', {
                    icon: '✨',
                    duration: 5000,
                  })
                }
              >
                <Plus size={14} />
                Add pairs
              </Button>
            </div>

            {/* Skeleton */}
            {datasetLoading && (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-14 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700 skeleton" />
                ))}
              </div>
            )}

            {/* Error */}
            {datasetError && !datasetLoading && (
              <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 text-xs text-red-600 dark:text-red-400">
                <strong>Backend error:</strong> {datasetError.message}
                <br />
                Make sure <code className="font-mono">GET /evaluation/dataset</code> is registered in your FastAPI app (see <code className="font-mono">backend_evaluation_route.py</code>).
              </div>
            )}

            {/* Empty state */}
            {!datasetLoading && !datasetError && pairs.length === 0 && (
              <EmptyState
                icon={<BookOpen className="w-full h-full" />}
                title="No golden pairs yet"
                description="Generate QA pairs automatically from your documents or add them manually."
                action={
                  <div className="space-y-1.5 text-xs text-surface-500 text-left">
                    <p>
                      <span className="font-semibold">Auto-generate:</span>{' '}
                      <code className="font-mono bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 rounded">
                        python scripts/generate_golden.py --auto-approve
                      </code>
                    </p>
                    <p>
                      <span className="font-semibold">Manual:</span> edit{' '}
                      <code className="font-mono bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 rounded">
                        data/golden_dataset/golden_qa.json
                      </code>
                    </p>
                  </div>
                }
              />
            )}

            {/* Pairs table */}
            {!datasetLoading && pairs.length > 0 && (
              <Card className="overflow-hidden p-0">
                {pairs.map((pair, i) => (
                  <GoldenPairRow key={i} pair={pair} index={i} />
                ))}
              </Card>
            )}

            {/* How-to callout */}
            {!datasetLoading && (
              <div className="p-4 rounded-xl bg-brand-50 dark:bg-brand-950/30 border border-brand-200 dark:border-brand-900">
                <p className="text-xs font-semibold text-brand-700 dark:text-brand-400 mb-2">
                  Three ways to grow your golden dataset
                </p>
                <div className="space-y-1.5 text-xs text-brand-600 dark:text-brand-500">
                  <p>
                    <strong>1. Auto-generate</strong> — uses your RAG pipeline to answer default seed questions and lets you approve each answer before saving.
                  </p>
                  <p>
                    <strong>2. From feedback</strong> — thumbs-up answers in chat flow into the dataset automatically via{' '}
                    <code className="font-mono bg-brand-100 dark:bg-brand-900 px-1 rounded">run_evaluation.py --add-feedback</code>.
                  </p>
                  <p>
                    <strong>3. Manual</strong> — directly edit{' '}
                    <code className="font-mono bg-brand-100 dark:bg-brand-900 px-1 rounded">data/golden_dataset/golden_qa.json</code>.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
