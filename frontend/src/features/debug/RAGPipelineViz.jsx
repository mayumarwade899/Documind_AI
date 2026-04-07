import { motion } from 'framer-motion'
import { cn } from '../../utils/cn.js'

const LAYERS = [
  {
    label: 'Ingestion',
    color: 'border-sky-400 dark:border-sky-600',
    bg:    'bg-sky-50 dark:bg-sky-950/40',
    text:  'text-sky-700 dark:text-sky-400',
    steps: ['PDF / TXT / DOCX', 'Chunker (800 tok)', 'Gemini Embedder', 'ChromaDB + BM25'],
  },
  {
    label: 'Retrieval',
    color: 'border-violet-400 dark:border-violet-600',
    bg:    'bg-violet-50 dark:bg-violet-950/40',
    text:  'text-violet-700 dark:text-violet-400',
    steps: ['Query Rewriter', 'Multi-Query (3–5)', 'Hybrid Search', 'Cross-Encoder Reranker'],
  },
  {
    label: 'Generation',
    color: 'border-emerald-400 dark:border-emerald-600',
    bg:    'bg-emerald-50 dark:bg-emerald-950/40',
    text:  'text-emerald-700 dark:text-emerald-400',
    steps: ['Prompt Builder', 'Gemini LLM', 'Citation Enforcer', 'Answer Verifier'],
  },
  {
    label: 'Evaluation',
    color: 'border-amber-400 dark:border-amber-600',
    bg:    'bg-amber-50 dark:bg-amber-950/40',
    text:  'text-amber-700 dark:text-amber-400',
    steps: ['Golden Dataset', 'RAGAS Metrics', 'Faithfulness', 'CI Quality Gate'],
  },
]

function LayerCard({ layer, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.3 }}
      className={cn(
        'rounded-xl border p-3 flex flex-col gap-2',
        layer.bg, layer.color
      )}
    >
      <p className={cn('text-[10px] font-bold uppercase tracking-widest', layer.text)}>
        {layer.label}
      </p>
      <div className="space-y-1">
        {layer.steps.map((step, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div className={cn('w-1 h-1 rounded-full shrink-0', layer.text.replace('text-', 'bg-'))} />
            <span className="text-[11px] text-surface-600 dark:text-surface-400">{step}</span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

export function RAGPipelineViz() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {LAYERS.map((layer, i) => (
        <LayerCard key={layer.label} layer={layer} index={i} />
      ))}
    </div>
  )
}
