import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, CheckCircle, AlertCircle, RefreshCw,
  Database, Layers, HardDrive, RotateCcw, MessageSquare, ArrowRight,
  Trash2, Search
} from 'lucide-react'
import toast from 'react-hot-toast'
import { useChatStore } from '../store/chatStore.js'

import { ingestFile, ingestDirectory, getIngestStatus, getDocuments, deleteDocument } from '../services/ingestService.js'
import { Button, Badge, Progress, Skeleton, EmptyState, Card } from '../components/ui/index.jsx'
import { formatBytes, formatLatency } from '../utils/format.js'
import { cn } from '../utils/cn.js'

function FileQueueItem({ item }) {
  const statusConfig = {
    pending: { icon: <div className="w-3.5 h-3.5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />, badge: 'info', label: 'Processing' },
    done: { icon: <CheckCircle size={14} className="text-emerald-500" />, badge: 'success', label: 'Ingested' },
    error: { icon: <AlertCircle size={14} className="text-red-500" />, badge: 'danger', label: 'Failed' },
    skipped: { icon: <CheckCircle size={14} className="text-surface-400" />, badge: 'default', label: 'Skipped (duplicate)' },
  }
  const cfg = statusConfig[item.status] ?? statusConfig.pending

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      className="flex items-center gap-3 p-3 rounded-xl border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850"
    >
      <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/50 flex items-center justify-center shrink-0">
        <FileText size={16} className="text-brand-600 dark:text-brand-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">{item.file.name}</p>
        <p className="text-xs text-surface-400 mt-0.5">{formatBytes(item.file.size)}</p>
        {item.progress != null && item.status === 'pending' && (
          <Progress value={item.progress} className="mt-1.5" />
        )}
        {item.error && <p className="text-xs text-red-500 mt-0.5">{item.error}</p>}
        {item.result && (
          <p className="text-xs text-surface-400 mt-0.5">
            {item.result.total_chunks} chunks · {item.result.total_pages} pages · {formatLatency(item.result.total_latency_ms)}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {cfg.icon}
        <Badge variant={cfg.badge} size="sm">{cfg.label}</Badge>
      </div>
    </motion.div>
  )
}

function DocumentRow({ doc, onDelete, isDeleting }) {
  const navigate = useNavigate()
  const { newConversation } = useChatStore()

  function handleDocumentChat() {
    const id = newConversation()
    navigate(`/chat/${id}`, { state: { document_id: doc.document_id, source_file: doc.source_file } })
  }

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-100 dark:border-surface-800 last:border-0 hover:bg-surface-50 dark:hover:bg-surface-800/40 transition-colors">
      <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/50 flex items-center justify-center shrink-0">
        <FileText size={14} className="text-brand-600 dark:text-brand-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">{doc.source_file}</p>
        <p className="text-xs text-surface-400 mt-0.5">{doc.chunk_count} chunks</p>
      </div>
      <Badge variant="brand" size="xs">{doc.chunk_count} chunks</Badge>
      <div className="flex items-center gap-1">
        <button
          onClick={handleDocumentChat}
          className="p-1.5 rounded-lg text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950/30 transition-colors"
          title="Chat with this document"
        >
          <MessageSquare size={13} />
        </button>
        <button
          onClick={() => onDelete(doc.document_id)}
          disabled={isDeleting}
          className="p-1.5 rounded-lg text-surface-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors disabled:opacity-40"
          title="Delete document"
        >
          {isDeleting ? <RefreshCw size={13} className="animate-spin" /> : <Trash2 size={13} />}
        </button>
      </div>
    </div>
  )
}

export default function DocumentsPage() {
  const navigate = useNavigate()
  const { newConversation } = useChatStore()
  const qc = useQueryClient()
  const [queue, setQueue] = useState([])
  const [forceReingest, setForceReingest] = useState(false)
  const [docSearch, setDocSearch] = useState('')
  const [deletingId, setDeletingId] = useState(null)

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['ingest-status'],
    queryFn: getIngestStatus,
    refetchInterval: 10_000,
  })

  const { data: docsData, isLoading: docsLoading } = useQuery({
    queryKey: ['ingested-documents'],
    queryFn: getDocuments,
    refetchInterval: 15_000,
  })

  const documents = (docsData?.documents ?? []).filter(d =>
    !docSearch || d.source_file.toLowerCase().includes(docSearch.toLowerCase())
  )

  async function handleDelete(documentId) {
    setDeletingId(documentId)
    try {
      const res = await deleteDocument(documentId)
      toast.success(`Deleted — ${res.chunks_deleted} chunks removed`)
      qc.invalidateQueries({ queryKey: ['ingested-documents'] })
      qc.invalidateQueries({ queryKey: ['ingest-status'] })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  function updateItem(id, updates) {
    setQueue(q => q.map(item => item.id === id ? { ...item, ...updates } : item))
  }

  async function processFile(file, id) {
    try {
      const result = await ingestFile(file, forceReingest, (progress) => updateItem(id, { progress }))
      const fileResult = result.file_results?.[0] ?? {}
      const status = fileResult.skipped ? 'skipped' : result.successful_files > 0 ? 'done' : 'error'
      updateItem(id, { status, result, error: fileResult.error })
      if (status === 'done') {
        toast.success(`${file.name} ingested — ${result.total_chunks} chunks`)
        qc.invalidateQueries({ queryKey: ['ingest-status'] })
        qc.invalidateQueries({ queryKey: ['ingested-documents'] })
      } else if (status === 'skipped') {
        toast(`${file.name} already indexed`, { icon: '📄' })
      } else {
        toast.error(`${file.name} failed`)
      }
    } catch (err) {
      updateItem(id, { status: 'error', error: err.message })
      toast.error(`${file.name}: ${err.message}`)
    }
  }

  const onDrop = (acceptedFiles) => {
    const newItems = acceptedFiles.map(file => ({
      id: Math.random().toString(36).slice(2),
      file,
      status: 'pending',
      progress: null,
      result: null,
      error: null,
    }))
    setQueue(q => [...newItems, ...q])
    newItems.forEach(item => processFile(item.file, item.id))
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxSize: 50 * 1024 * 1024,
    onDropRejected: (files) => {
      files.forEach(({ file, errors }) => toast.error(`${file.name}: ${errors[0]?.message}`))
    },
  })

  const scanMutation = useMutation({
    mutationFn: () => ingestDirectory('data/documents', forceReingest),
    onSuccess: (res) => {
      toast.success(`Directory scan complete — ${res.successful_files} files, ${res.total_chunks} chunks`)
      qc.invalidateQueries({ queryKey: ['ingest-status'] })
      qc.invalidateQueries({ queryKey: ['ingested-documents'] })
    },
    onError: (err) => toast.error(err.message),
  })

  const vectorChunks = status?.vector_store?.total_chunks ?? 0
  const bm25Chunks = status?.bm25_index?.total_chunks ?? 0

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between h-14 px-6 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
        <div>
          <h1 className="text-base font-semibold text-surface-900 dark:text-white">Documents</h1>
          <p className="text-xs text-surface-400">Ingest and manage your knowledge base</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-surface-500 cursor-pointer">
            <div
              onClick={() => setForceReingest(!forceReingest)}
              className={cn(
                'w-7 h-3.5 rounded-full transition-colors cursor-pointer relative',
                forceReingest ? 'bg-amber-500' : 'bg-surface-200 dark:bg-surface-700'
              )}
            >
              <div className={cn('absolute top-0.5 w-2.5 h-2.5 bg-white rounded-full shadow-sm transition-transform', forceReingest ? 'translate-x-3.5' : 'translate-x-0.5')} />
            </div>
            Force re-ingest
          </label>
          <Button variant="secondary" size="sm" onClick={() => scanMutation.mutate()} disabled={scanMutation.isPending}>
            <RotateCcw size={14} className={cn(scanMutation.isPending && 'animate-spin')} />
            Scan directory
          </Button>
          <button
            onClick={() => {
              const id = newConversation()
              navigate(`/chat/${id}`)
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-brand-500 dark:border-brand-600 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950/40 transition-all"
          >
            <MessageSquare size={13} />
            Go to Chat
            <ArrowRight size={11} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: <Database size={16} />, label: 'Vector chunks', value: vectorChunks.toLocaleString(), color: 'text-brand-600 dark:text-brand-400', bg: 'bg-brand-50 dark:bg-brand-950/50' },
            { icon: <Layers size={16} />, label: 'BM25 chunks', value: bm25Chunks.toLocaleString(), color: 'text-sky-600 dark:text-sky-400', bg: 'bg-sky-50 dark:bg-sky-950/50' },
            { icon: <HardDrive size={16} />, label: 'Index built', value: status?.bm25_index?.index_built ? 'Ready' : 'Empty', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/50' },
          ].map(c => (
            <div key={c.label} className="bg-white dark:bg-surface-850 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
              <div className={cn('inline-flex p-2 rounded-lg mb-2', c.bg)}>
                <span className={c.color}>{c.icon}</span>
              </div>
              {statusLoading
                ? <Skeleton className="h-7 w-16 mb-1" />
                : <p className="text-2xl font-semibold text-surface-900 dark:text-white">{c.value}</p>}
              <p className="text-xs text-surface-400">{c.label}</p>
            </div>
          ))}
        </div>

        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200',
            isDragActive
              ? 'border-brand-500 bg-brand-50 dark:bg-brand-950/30 scale-[1.01]'
              : 'border-surface-200 dark:border-surface-700 hover:border-brand-400 dark:hover:border-brand-600 hover:bg-surface-50 dark:hover:bg-surface-800/50'
          )}
        >
          <input {...getInputProps()} />
          <div className={cn('w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-colors', isDragActive ? 'bg-brand-100 dark:bg-brand-900' : 'bg-surface-100 dark:bg-surface-800')}>
            <Upload size={22} className={isDragActive ? 'text-brand-600' : 'text-surface-400'} />
          </div>
          <p className="font-semibold text-surface-700 dark:text-surface-300 mb-1">
            {isDragActive ? 'Drop to ingest' : 'Drag & drop documents'}
          </p>
          <p className="text-sm text-surface-400">or click to browse · PDF, TXT, DOCX · max 50 MB</p>
        </div>

        {queue.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Upload queue</h2>
              <button onClick={() => setQueue([])} className="text-xs text-surface-400 hover:text-surface-600 dark:hover:text-surface-300">Clear</button>
            </div>
            <div className="space-y-2">
              <AnimatePresence>
                {queue.map(item => <FileQueueItem key={item.id} item={item} />)}
              </AnimatePresence>
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">
              Ingested documents
              {!docsLoading && <span className="ml-2 text-surface-400 font-normal">({docsData?.documents?.length ?? 0})</span>}
            </h2>
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-400" />
              <input
                type="text"
                placeholder="Filter documents..."
                value={docSearch}
                onChange={e => setDocSearch(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 text-surface-700 dark:text-surface-300 placeholder:text-surface-400 focus:outline-none focus:ring-1 focus:ring-brand-500 w-48"
              />
            </div>
          </div>

          {docsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-xl" />)}
            </div>
          ) : documents.length === 0 ? (
            <Card className="p-8 text-center">
              <Database size={24} className="mx-auto text-surface-300 dark:text-surface-600 mb-2" />
              <p className="text-sm text-surface-400">
                {docSearch ? 'No documents match your filter' : 'No documents ingested yet. Upload files above to get started.'}
              </p>
            </Card>
          ) : (
            <Card className="overflow-hidden p-0">
              {documents.map(doc => (
                <DocumentRow
                  key={doc.document_id}
                  doc={doc}
                  onDelete={handleDelete}
                  isDeleting={deletingId === doc.document_id}
                />
              ))}
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
