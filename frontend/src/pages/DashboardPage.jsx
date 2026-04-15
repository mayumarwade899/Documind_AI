import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  MessageSquare, FileText, BarChart3, FlaskConical,
  Zap, CheckCircle, DollarSign, Hash, ArrowRight,
  Plus, Upload, ShieldCheck
} from 'lucide-react'
import { getMetrics, getHealthStatus } from '../services/metricsService.js'
import { getIngestStatus } from '../services/ingestService.js'
import { useChatStore } from '../store/chatStore.js'
import { MetricCard } from '../components/shared/index.jsx'
import { Badge, Skeleton, Card } from '../components/ui/index.jsx'
import { RAGPipelineViz } from '../features/debug/RAGPipelineViz.jsx'
import { formatCost, formatLatency, formatPercent } from '../utils/format.js'

function QuickAction({ icon, label, description, to, onClick, color }) {
  const navigate = useNavigate()
  return (
    <motion.button
      whileHover={{ y: -2 }}
      onClick={onClick || (() => navigate(to))}
      className="flex items-start gap-3 p-4 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700 hover:border-brand-400 dark:hover:border-brand-600 hover:shadow-card-hover transition-all text-left w-full"
    >
      <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-surface-800 dark:text-surface-200">{label}</p>
        <p className="text-xs text-surface-400 mt-0.5">{description}</p>
      </div>
      <ArrowRight size={14} className="text-surface-300 dark:text-surface-600 mt-1 shrink-0" />
    </motion.button>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { conversations, newConversation } = useChatStore()

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metrics', 7],
    queryFn: () => getMetrics(7),
    refetchInterval: 60_000,
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealthStatus,
    refetchInterval: 30_000,
  })

  const { data: ingestStatus } = useQuery({
    queryKey: ['ingest-status'],
    queryFn: getIngestStatus,
  })

  function handleNewChat() {
    const id = newConversation()
    navigate(`/chat/${id}`)
  }

  const vectorChunks = ingestStatus?.vector_store?.total_chunks ?? 0

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-8 pt-8 pb-6 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-semibold text-surface-900 dark:text-white">Dashboard</h1>
              {health && (
                <Badge variant="success" size="sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-soft" />
                  {health.status}
                </Badge>
              )}
            </div>
            <p className="text-sm text-surface-400">
              RAG system overview and metrics
            </p>
          </div>
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors shadow-glow-sm"
          >
            <Plus size={15} />
            New chat
          </button>
        </div>
      </div>

      <div className="px-8 py-6 space-y-7">
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-3">Last 7 days</h2>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {metricsLoading ? (
              Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
            ) : metrics ? (
              <>
                <MetricCard icon={<Hash size={16} />} label="Total queries" value={metrics.total_requests?.toLocaleString() ?? '0'} sub={`${metrics.successful} succeeded`} color="brand" />
                <MetricCard icon={<Zap size={16} />} label="p95 latency" value={formatLatency(metrics.latency?.p95_ms)} sub={`avg ${formatLatency(metrics.latency?.avg_ms)}`} color="amber" />
                <MetricCard icon={<ShieldCheck size={16} />} label="Groundedness" value={formatPercent(metrics.avg_support_ratio)} sub="avg support ratio" color="violet" />
                <MetricCard icon={<DollarSign size={16} />} label="Total cost" value={formatCost(metrics.total_cost_usd)} sub={`${formatCost(metrics.avg_cost_usd)} / request`} color="emerald" />
                <MetricCard icon={<CheckCircle size={16} />} label="Success rate" value={formatPercent(metrics.success_rate)} sub={`${metrics.failed} failed`} color="sky" />
              </>
            ) : (
              <div className="col-span-2 lg:col-span-5">
                <Card className="p-6 text-center">
                  <p className="text-sm text-surface-400">No metrics yet. Send your first query to see stats here.</p>
                </Card>
              </div>
            )}
          </div>
        </section>

        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-3">Quick actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <QuickAction
              icon={<MessageSquare size={16} className="text-brand-600 dark:text-brand-400" />}
              label="Ask your documents"
              description="Chat with your knowledge base using hybrid RAG"
              onClick={handleNewChat}
              color="bg-brand-50 dark:bg-brand-950/50"
            />
            <QuickAction
              icon={<Upload size={16} className="text-sky-600 dark:text-sky-400" />}
              label="Upload documents"
              description="Ingest PDFs, TXT or DOCX into the vector store"
              to="/documents"
              color="bg-sky-50 dark:bg-sky-950/50"
            />
            <QuickAction
              icon={<FlaskConical size={16} className="text-violet-600 dark:text-violet-400" />}
              label="Run evaluation"
              description="RAGAS quality gate against the golden dataset"
              to="/evaluation"
              color="bg-violet-50 dark:bg-violet-950/50"
            />
            <QuickAction
              icon={<BarChart3 size={16} className="text-emerald-600 dark:text-emerald-400" />}
              label="View monitoring"
              description="Latency, cost, tokens and feedback analytics"
              to="/monitoring"
              color="bg-emerald-50 dark:bg-emerald-950/50"
            />
          </div>
        </section>

        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-3">Recent conversations</h2>
          {conversations.length === 0 ? (
            <Card className="p-6 text-center">
              <MessageSquare size={24} className="mx-auto text-surface-300 dark:text-surface-600 mb-2" />
              <p className="text-sm text-surface-400">No conversations yet. Start chatting!</p>
            </Card>
          ) : (
            <div className="space-y-2">
              {conversations.slice(0, 5).map(conv => (
                <motion.button
                  key={conv.id}
                  whileHover={{ x: 2 }}
                  onClick={() => navigate(`/chat/${conv.id}`)}
                  className="w-full flex items-center gap-3 p-3 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700 hover:border-brand-400 dark:hover:border-brand-600 text-left transition-all"
                >
                  <div className="w-7 h-7 rounded-full bg-brand-100 dark:bg-brand-950 flex items-center justify-center shrink-0">
                    <MessageSquare size={13} className="text-brand-600 dark:text-brand-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">{conv.title}</p>
                    <p className="text-xs text-surface-400">{conv.messages.length} messages</p>
                  </div>
                  <ArrowRight size={13} className="text-surface-300 dark:text-surface-600 shrink-0" />
                </motion.button>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-3">Pipeline architecture</h2>
          <RAGPipelineViz />
        </section>

      </div>
    </div>
  )
}
