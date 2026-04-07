import { useState } from 'react'
import { X, Search, Layers, Cpu, GitBranch, CheckCircle, AlertCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Tabs, Badge } from '../../components/ui/index.jsx'
import { cn } from '../../utils/cn.js'
import { formatLatency, formatPercent } from '../../utils/format.js'

export function DebugPanel({ response, onClose }) {
  const [tab, setTab] = useState('retrieval')
  if (!response) return null

  const { metrics, verification, sources } = response

  const tabs = [
    { id: 'retrieval', label: 'Retrieval', icon: <Search size={12} /> },
    { id: 'chunks',    label: 'Chunks',    icon: <Layers size={12} />, count: sources?.length },
    { id: 'pipeline',  label: 'Pipeline',  icon: <Cpu size={12} /> },
    { id: 'verify',    label: 'Verify',    icon: <CheckCircle size={12} /> },
  ]

  return (
    <motion.aside
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.2 }}
      className="w-72 border-l border-surface-200 dark:border-surface-700 flex flex-col bg-surface-50 dark:bg-surface-900 shrink-0 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-surface-200 dark:border-surface-700 shrink-0">
        <div className="flex items-center gap-2">
          <GitBranch size={14} className="text-brand-500" />
          <span className="text-xs font-semibold text-surface-700 dark:text-surface-300">Debug panel</span>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-200 dark:hover:bg-surface-700 text-surface-400 transition-colors">
          <X size={14} />
        </button>
      </div>

      {/* Tabs */}
      <div className="px-3 py-2 border-b border-surface-200 dark:border-surface-700 shrink-0">
        <Tabs tabs={tabs} active={tab} onChange={setTab} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        {tab === 'retrieval' && <RetrievalTab metrics={metrics} />}
        {tab === 'chunks'    && <ChunksTab sources={sources} />}
        {tab === 'pipeline'  && <PipelineTab metrics={metrics} />}
        {tab === 'verify'    && <VerifyTab verification={verification} />}
      </div>
    </motion.aside>
  )
}

function SectionLabel({ children }) {
  return <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-2">{children}</p>
}

function Row({ label, value, mono = false }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-surface-100 dark:border-surface-800 last:border-0">
      <span className="text-surface-500">{label}</span>
      <span className={cn('font-medium text-surface-800 dark:text-surface-200', mono && 'font-mono')}>{value ?? '—'}</span>
    </div>
  )
}

function RetrievalTab({ metrics }) {
  if (!metrics) return <p className="text-surface-400">No retrieval data.</p>
  return (
    <>
      <SectionLabel>Retrieval stats</SectionLabel>
      <div className="bg-white dark:bg-surface-850 rounded-lg border border-surface-200 dark:border-surface-700 px-3 divide-y divide-surface-100 dark:divide-surface-800">
        <Row label="Queries used"     value={metrics.num_queries_used} />
        <Row label="Chunks retrieved" value={metrics.num_chunks_retrieved} />
        <Row label="Chunks used"      value={metrics.num_chunks_used} />
        <Row label="Retrieval time"   value={formatLatency(metrics.retrieval_latency_ms)} />
      </div>
      <SectionLabel>Methods</SectionLabel>
      <div className="flex flex-wrap gap-1.5">
        {metrics.retrieval_methods?.map(m => (
          <Badge key={m} variant={m === 'hybrid' ? 'brand' : m === 'vector' ? 'info' : 'default'}>
            {m}
          </Badge>
        ))}
      </div>
    </>
  )
}

function ChunksTab({ sources }) {
  if (!sources?.length) return <p className="text-surface-400">No chunks used.</p>
  return (
    <div className="space-y-2">
      {sources.map((s, i) => (
        <div key={i} className="bg-white dark:bg-surface-850 rounded-lg border border-surface-200 dark:border-surface-700 p-2.5 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-medium text-surface-700 dark:text-surface-300 truncate pr-2">{s.source_file}</span>
            <span className="font-semibold text-brand-600 dark:text-brand-400 tabular-nums shrink-0">
              {(s.relevance_score * 100).toFixed(1)}%
            </span>
          </div>
          <div className="h-1 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 rounded-full" style={{ width: `${s.relevance_score * 100}%` }} />
          </div>
          <div className="flex items-center gap-2 text-[10px] text-surface-400">
            <span>p.{s.page_number}</span>
            <span className="font-mono opacity-70">{s.chunk_id?.slice(-8)}</span>
          </div>
          <p className="text-[10px] text-surface-500 dark:text-surface-400 line-clamp-3 leading-relaxed">
            {s.content_preview}
          </p>
        </div>
      ))}
    </div>
  )
}

function PipelineTab({ metrics }) {
  if (!metrics) return <p className="text-surface-400">No pipeline data.</p>
  const steps = [
    { label: 'Retrieval',   ms: metrics.retrieval_latency_ms,   color: 'bg-sky-400' },
    { label: 'Reranking',   ms: metrics.reranking_latency_ms,   color: 'bg-brand-400' },
    { label: 'Generation',  ms: metrics.generation_latency_ms,  color: 'bg-emerald-400' },
  ]
  const total = metrics.total_latency_ms || 1
  return (
    <>
      <SectionLabel>Latency breakdown</SectionLabel>
      <div className="space-y-2">
        {steps.map(s => (
          <div key={s.label}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-surface-500">{s.label}</span>
              <span className="font-mono font-medium text-surface-700 dark:text-surface-300">{formatLatency(s.ms)}</span>
            </div>
            <div className="h-1.5 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
              <div className={cn('h-full rounded-full', s.color)} style={{ width: `${(s.ms / total) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 pt-3 border-t border-surface-200 dark:border-surface-700">
        <SectionLabel>Tokens</SectionLabel>
        <div className="bg-white dark:bg-surface-850 rounded-lg border border-surface-200 dark:border-surface-700 px-3 divide-y divide-surface-100 dark:divide-surface-800">
          <Row label="Input"  value={metrics.input_tokens?.toLocaleString()}  mono />
          <Row label="Output" value={metrics.output_tokens?.toLocaleString()} mono />
          <Row label="Total"  value={metrics.total_tokens?.toLocaleString()}  mono />
        </div>
      </div>
    </>
  )
}

function VerifyTab({ verification }) {
  if (!verification) return <p className="text-surface-400">No verification data.</p>
  return (
    <>
      <SectionLabel>Verification result</SectionLabel>
      <div className="flex items-center gap-2 mb-3">
        {verification.is_fully_supported
          ? <CheckCircle size={16} className="text-emerald-500" />
          : <AlertCircle size={16} className="text-amber-500" />}
        <span className={cn('font-semibold', verification.is_fully_supported ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400')}>
          {verification.is_fully_supported ? 'Fully supported' : 'Partially supported'}
        </span>
      </div>

      <div className="bg-white dark:bg-surface-850 rounded-lg border border-surface-200 dark:border-surface-700 px-3 divide-y divide-surface-100 dark:divide-surface-800">
        <Row label="Support ratio" value={formatPercent(verification.support_ratio)} />
        <Row label="Confidence"    value={formatPercent(verification.confidence)} />
        <Row label="Citations"     value={verification.citation_count} />
        <Row label="Has citations" value={verification.has_citations ? 'Yes' : 'No'} />
      </div>

      {verification.unsupported_claims?.length > 0 && (
        <div className="mt-3">
          <SectionLabel>Unsupported claims</SectionLabel>
          <div className="space-y-1.5">
            {verification.unsupported_claims.map((c, i) => (
              <div key={i} className="flex gap-2 p-2 bg-red-50 dark:bg-red-950/30 rounded-lg border border-red-200 dark:border-red-900">
                <AlertCircle size={12} className="text-red-500 shrink-0 mt-0.5" />
                <p className="text-[10px] text-red-700 dark:text-red-400 leading-relaxed">{c}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
