import { useQuery } from '@tanstack/react-query'
import { Settings as SettingsIcon, Sliders, Server, BookOpen, Layers } from 'lucide-react'
import { api } from '../services/api.js'
import { Card, Skeleton } from '../components/ui/index.jsx'
import { cn } from '../utils/cn.js'

function SettingsSection({ title, icon, children }) {
  return (
    <Card className="p-0 overflow-hidden mb-6">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-surface-200 dark:border-surface-700 bg-surface-50/50 dark:bg-surface-800/30">
        <span className="text-brand-500">{icon}</span>
        <h3 className="text-sm font-semibold text-surface-800 dark:text-surface-200">{title}</h3>
      </div>
      <div className="p-5">
        {children}
      </div>
    </Card>
  )
}

function SettingRow({ label, value, type = 'text' }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-surface-100 dark:border-surface-800 last:border-0 last:pb-0 font-sm">
      <span className="text-surface-600 dark:text-surface-400 capitalize">{label.replace(/_/g, ' ')}</span>
      <span className={cn('text-surface-900 dark:text-surface-100 font-medium', type === 'number' && 'font-mono text-brand-600 dark:text-brand-400')}>
        {value}
      </span>
    </div>
  )
}

export default function SettingsPage() {
  const { data: settings, isLoading } = useQuery({
    queryKey: ['system-settings'],
    queryFn: () => api.get('/settings'),
  })

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between h-14 px-6 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
        <div>
          <h1 className="text-base font-semibold text-surface-900 dark:text-white">System Settings</h1>
          <p className="text-xs text-surface-400">Read-only view of backend configuration (.env)</p>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl mx-auto">
          {isLoading ? (
            <div className="space-y-6">
              {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-40 rounded-xl" />)}
            </div>
          ) : !settings ? (
            <div className="text-center p-8 bg-surface-50 dark:bg-surface-800 rounded-xl">
              <p className="text-surface-500">Failed to load settings</p>
            </div>
          ) : (
            <>
              <SettingsSection title="LLM & embedding (Gemini)" icon={<Server size={16} />}>
                <SettingRow label="Model" value={settings.gemini.model} />
                <SettingRow label="Embedding model" value={settings.gemini.embedding_model} />
                <SettingRow label="Temperature" value={settings.gemini.temperature} type="number" />
                <SettingRow label="Max tokens" value={settings.gemini.max_tokens} type="number" />
              </SettingsSection>

              <SettingsSection title="Text chunking" icon={<Layers size={16} />}>
                <SettingRow label="Chunk size (tokens)" value={settings.chunking.chunk_size} type="number" />
                <SettingRow label="Chunk overlap" value={settings.chunking.chunk_overlap} type="number" />
              </SettingsSection>

              <SettingsSection title="Retrieval parameters" icon={<Sliders size={16} />}>
                <SettingRow label="Vector search Top K" value={settings.retrieval.vector_search_top_k} type="number" />
                <SettingRow label="BM25 search Top K" value={settings.retrieval.bm25_search_top_k} type="number" />
                <SettingRow label="Final Top K (after reranking)" value={settings.retrieval.final_top_k} type="number" />
                <SettingRow label="Multi-query permutations" value={settings.retrieval.multi_query_count} type="number" />
              </SettingsSection>

              <SettingsSection title="Evaluation thresholds" icon={<BookOpen size={16} />}>
                <SettingRow label="Min faithfulness score" value={settings.evaluation.min_faithfulness_score} type="number" />
                <SettingRow label="Min context relevance score" value={settings.evaluation.min_context_relevance_score} type="number" />
                <SettingRow label="Min answer correctness score" value={settings.evaluation.min_answer_correctness_score} type="number" />
              </SettingsSection>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
