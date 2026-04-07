import { useState } from 'react'
import { FileText, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { cn } from '../../utils/cn.js'

export function CitationCard({ source, index }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-surface-50 dark:bg-surface-800/60 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors text-left"
      >
        <div className="flex items-center justify-center w-4 h-4 rounded-full bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300 text-[9px] font-bold shrink-0">
          {index}
        </div>
        <FileText size={12} className="text-surface-400 shrink-0" />
        <span className="flex-1 font-medium text-surface-700 dark:text-surface-300 truncate">
          {source.source_file}
        </span>
        <span className="text-surface-400 shrink-0 font-mono">p.{source.page_number}</span>
        <span className="ml-1 text-brand-500 font-semibold shrink-0">
          {(source.relevance_score * 100).toFixed(0)}%
        </span>
        {expanded ? <ChevronUp size={12} className="text-surface-400 shrink-0" /> : <ChevronDown size={12} className="text-surface-400 shrink-0" />}
      </button>

      {expanded && (
        <div className="px-3 py-2.5 bg-white dark:bg-surface-850 border-t border-surface-200 dark:border-surface-700">
          <p className="text-surface-600 dark:text-surface-400 leading-relaxed">
            {source.content_preview}
          </p>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-surface-400 font-mono">chunk: {source.chunk_id?.slice(-8)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
