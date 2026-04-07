import { motion } from 'framer-motion'
import { Search, GitBranch, Layers, Cpu, MessageSquare, CheckCircle, Clock } from 'lucide-react'
import { cn } from '../../utils/cn.js'
import { formatLatency } from '../../utils/format.js'

const STEPS = [
  { id: 'rewrite',    icon: GitBranch,     label: 'Query rewrite',  color: 'text-violet-500',  bg: 'bg-violet-50 dark:bg-violet-950/50' },
  { id: 'retrieval',  icon: Search,        label: 'Hybrid retrieval', color: 'text-sky-500',   bg: 'bg-sky-50 dark:bg-sky-950/50' },
  { id: 'reranking',  icon: Layers,        label: 'Reranking',       color: 'text-amber-500',  bg: 'bg-amber-50 dark:bg-amber-950/50' },
  { id: 'generation', icon: MessageSquare, label: 'Generation',      color: 'text-emerald-500',bg: 'bg-emerald-50 dark:bg-emerald-950/50' },
  { id: 'verify',     icon: CheckCircle,   label: 'Verification',    color: 'text-brand-500',  bg: 'bg-brand-50 dark:bg-brand-950/50' },
]

function StepNode({ step, latency, status, index }) {
  const Icon = step.icon
  const isActive  = status === 'active'
  const isDone    = status === 'done'
  const isPending = status === 'pending'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: isPending ? 0.35 : 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="flex flex-col items-center gap-1.5"
    >
      <div className={cn(
        'w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-300',
        isDone    ? step.bg + ' ring-1 ring-current/20'  : '',
        isActive  ? step.bg + ' ring-2 ring-offset-1 dark:ring-offset-surface-900 animate-pulse-soft' : '',
        isPending ? 'bg-surface-100 dark:bg-surface-800' : '',
      )}>
        {isActive ? (
          <div className="w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" style={{ color: 'currentColor' }}>
            <Icon size={0} className={step.color} />
          </div>
        ) : (
          <Icon size={16} className={isDone ? step.color : 'text-surface-300 dark:text-surface-600'} />
        )}
      </div>
      <span className={cn(
        'text-[10px] font-medium text-center leading-tight max-w-[64px]',
        isDone   ? 'text-surface-700 dark:text-surface-300' : '',
        isActive ? 'text-surface-800 dark:text-surface-200' : '',
        isPending ? 'text-surface-300 dark:text-surface-600' : '',
      )}>
        {step.label}
      </span>
      {isDone && latency != null && (
        <span className="text-[9px] font-mono text-surface-400">{formatLatency(latency)}</span>
      )}
    </motion.div>
  )
}

function Connector({ done }) {
  return (
    <div className="flex-1 h-px mt-[-18px] mx-1">
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: done ? 1 : 0 }}
        transition={{ duration: 0.3 }}
        className="h-full bg-surface-300 dark:bg-surface-600 origin-left"
      />
      {!done && <div className="h-full bg-surface-200 dark:bg-surface-700" />}
    </div>
  )
}

/**
 * PipelineTrace
 *
 * Props:
 *   activeStep: 'rewrite' | 'retrieval' | 'reranking' | 'generation' | 'verify' | 'done' | null
 *   metrics: { retrieval_latency_ms, reranking_latency_ms, generation_latency_ms }
 */
export function PipelineTrace({ activeStep, metrics }) {
  const stepOrder = STEPS.map(s => s.id)
  const activeIdx = activeStep === 'done' ? STEPS.length : stepOrder.indexOf(activeStep)

  return (
    <div className="flex items-start gap-0 py-2 px-1">
      {STEPS.map((step, i) => {
        let status = 'pending'
        if (i < activeIdx)  status = 'done'
        if (i === activeIdx && activeStep !== 'done') status = 'active'

        const latencyMap = {
          retrieval:  metrics?.retrieval_latency_ms,
          reranking:  metrics?.reranking_latency_ms,
          generation: metrics?.generation_latency_ms,
        }

        return (
          <div key={step.id} className="flex items-center flex-1 min-w-0">
            <StepNode
              step={step}
              latency={latencyMap[step.id]}
              status={status}
              index={i}
            />
            {i < STEPS.length - 1 && <Connector done={i < activeIdx} />}
          </div>
        )
      })}
    </div>
  )
}
