import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { GitBranch, MessageSquare, FileText, ChevronDown, X, Upload } from 'lucide-react'
import toast from 'react-hot-toast'

import { useChatStore } from '../store/chatStore.js'
import { useUIStore } from '../store/uiStore.js'
import { queryRAG, submitFeedback } from '../services/queryService.js'
import { getDocuments } from '../services/ingestService.js'

import { ConversationList } from '../features/chat/ConversationList.jsx'
import { MessageBubble, StreamingBubble } from '../features/chat/MessageBubble.jsx'
import { ChatInput } from '../features/chat/ChatInput.jsx'
import { DebugPanel } from '../features/debug/DebugPanel.jsx'
import { PipelineTrace } from '../features/debug/PipelineTrace.jsx'
import { Button } from '../components/ui/index.jsx'

const STARTERS = [
  'What are the main findings of this document?',
  'Summarise the key recommendations',
  'What methodology or approach was used?',
  'List all limitations mentioned',
  'Who created this document and when?',
  'What are the next steps described?',
]

export default function ChatPage() {
  const { conversationId } = useParams()
  const navigate = useNavigate()

  const {
    conversations,
    activeConversationId,
    newConversation,
    addMessage,
    updateLastMessage,
    setActiveConversation,
  } = useChatStore()

  const { debugPanelOpen, toggleDebugPanel } = useUIStore()

  const [lastResponse, setLastResponse] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(null)

  const [documents, setDocuments] = useState([])
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [docDropdownOpen, setDocDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (conversationId) setActiveConversation(conversationId)
  }, [conversationId, setActiveConversation])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeConversationId, conversations])

  useEffect(() => {
    getDocuments()
      .then((res) => setDocuments(res.documents ?? []))
      .catch(() => { })
  }, [])

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDocDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const activeConv =
    conversations.find(
      (c) => c.id === (conversationId ?? activeConversationId)
    ) ?? null

  const hasMessages = (activeConv?.messages?.length ?? 0) > 0

  const selectedDoc = documents.find((d) => d.document_id === selectedDocId)

  const pipelineTimers = useRef([])

  function clearPipelineTimers() {
    pipelineTimers.current.forEach(clearTimeout)
    pipelineTimers.current = []
  }

  async function handleSend(query, options = {}) {
    let convId = conversationId ?? activeConversationId
    if (!convId) {
      convId = newConversation()
      navigate(`/chat/${convId}`)
      await new Promise((r) => setTimeout(r, 40))
    }

    setIsLoading(true)
    setLastResponse(null)
    clearPipelineTimers()
    setPipelineStep('rewrite')
    addMessage(convId, { role: 'user', content: query })

    pipelineTimers.current.push(setTimeout(() => setPipelineStep('retrieval'), 600))
    pipelineTimers.current.push(setTimeout(() => setPipelineStep('reranking'), 2000))

    try {
      const response = await queryRAG({
        query,
        use_query_rewriting: options.use_query_rewriting ?? true,
        use_multi_query: options.use_multi_query ?? true,
        verify_answer: options.verify_answer ?? true,
        document_id: selectedDocId || undefined,
      })

      clearPipelineTimers()
      setPipelineStep('reranking')
      await new Promise((r) => setTimeout(r, 400))
      setPipelineStep('generation')
      await new Promise((r) => setTimeout(r, 400))
      setPipelineStep('verify')
      await new Promise((r) => setTimeout(r, 400))
      setPipelineStep('done')

      setLastResponse(response)

      addMessage(convId, {
        role: 'assistant',
        content: response.answer,
        sources: response.sources ?? [],
        verification: response.verification ?? null,
        metrics: response.metrics ?? null,
        rewrittenQuery: response.rewritten_query ?? null,
        success: response.success,
      })
    } catch (err) {
      clearPipelineTimers()
      setPipelineStep(null)
      const msg = err.message ?? 'Query failed. Please try again.'
      toast.error(msg)
      addMessage(convId, {
        role: 'assistant',
        content: `Unable to process your query: ${msg}`,
        success: false,
      })
    } finally {
      setIsLoading(false)
      setTimeout(() => setPipelineStep(null), 2000)
    }
  }

  async function handleFeedback(messageIndex, sentiment) {
    if (!activeConv) return
    const msg = activeConv.messages[messageIndex]
    if (!msg || msg.role !== 'assistant') return

    updateLastMessage(activeConv.id, { feedback: sentiment })

    const userMsg = [...activeConv.messages]
      .slice(0, messageIndex)
      .reverse()
      .find((m) => m.role === 'user')

    try {
      await submitFeedback({
        query: userMsg?.content ?? '',
        answer: msg.content ?? '',
        rating: sentiment === 'positive' ? 1 : -1,
        sources: msg.sources ?? [],
        rewritten_query: msg.rewrittenQuery ?? '',
        num_chunks_used: msg.metrics?.num_chunks_used ?? 0,
        total_latency_ms: msg.metrics?.total_latency_ms ?? 0,
        model_used: 'gemini',
      })
      toast.success(
        sentiment === 'positive' ? 'Thanks for the feedback!' : 'Feedback noted'
      )
    } catch {
      toast.error('Could not save feedback')
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: conversation list */}
      <div className="w-52 shrink-0 border-r border-surface-200 dark:border-surface-700 flex flex-col bg-white dark:bg-surface-900">
        <div className="flex items-center h-11 px-3 border-b border-surface-200 dark:border-surface-700 shrink-0">
          <span className="text-xs font-semibold uppercase tracking-wide text-surface-400">
            History
          </span>
        </div>
        <ConversationList />
      </div>

      {/* Centre: chat */}
      <div className="flex-1 flex flex-col min-w-0 bg-surface-50 dark:bg-surface-950">
        {/* Top bar */}
        <div className="flex items-center justify-between h-11 px-4 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
          <span className="text-sm font-medium text-surface-700 dark:text-surface-300 truncate max-w-sm">
            {activeConv?.title ?? 'Chat'}
          </span>
          <div className="flex items-center gap-1.5">
            {/* Document selector */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDocDropdownOpen(!docDropdownOpen)}
                className={`
                  flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border transition-all
                  ${selectedDocId
                    ? 'border-brand-400 dark:border-brand-500 bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300'
                    : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 text-surface-500 dark:text-surface-400 hover:border-surface-300 dark:hover:border-surface-600'
                  }
                `}
              >
                <FileText size={12} />
                <span className="max-w-[120px] truncate">
                  {selectedDoc ? selectedDoc.source_file : 'All documents'}
                </span>
                <ChevronDown size={11} className={`transition-transform ${docDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {docDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -4, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.97 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-1 w-64 max-h-60 overflow-y-auto rounded-xl border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 shadow-xl z-50"
                  >
                    <div className="p-1">
                      <button
                        onClick={() => { setSelectedDocId(null); setDocDropdownOpen(false) }}
                        className={`
                          w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors
                          ${!selectedDocId
                            ? 'bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300'
                            : 'text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-800'
                          }
                        `}
                      >
                        <FileText size={13} className="shrink-0 opacity-50" />
                        <span className="truncate font-medium">All documents</span>
                      </button>

                      {documents.length > 0 && (
                        <div className="h-px bg-surface-100 dark:bg-surface-700 my-1" />
                      )}

                      {documents.map((doc) => (
                        <button
                          key={doc.document_id}
                          onClick={() => { setSelectedDocId(doc.document_id); setDocDropdownOpen(false) }}
                          className={`
                            w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors
                            ${selectedDocId === doc.document_id
                              ? 'bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300'
                              : 'text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-800'
                            }
                          `}
                        >
                          <FileText size={13} className="shrink-0 text-brand-500 dark:text-brand-400" />
                          <div className="flex flex-col items-start min-w-0">
                            <span className="truncate w-full font-medium">{doc.source_file}</span>
                            <span className="text-[10px] text-surface-400">{doc.chunk_count} chunks</span>
                          </div>
                        </button>
                      ))}

                      {documents.length === 0 && (
                        <div className="px-3 py-3 text-xs text-surface-400 text-center">
                          No documents ingested yet
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {selectedDocId && (
              <button
                onClick={() => setSelectedDocId(null)}
                className="p-1 rounded-md text-surface-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                title="Clear document filter"
              >
                <X size={13} />
              </button>
            )}

            {lastResponse && (
              <Button
                variant="ghost"
                size="xs"
                onClick={toggleDebugPanel}
                className={
                  debugPanelOpen
                    ? 'text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/50'
                    : ''
                }
              >
                <GitBranch size={13} />
                Debug
              </Button>
            )}

            <button
              onClick={() => navigate('/documents')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-brand-500 dark:border-brand-600 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950/40 transition-all"
            >
              <Upload size={12} />
              Upload docs
            </button>
          </div>
        </div>

        {/* Document filter indicator */}
        <AnimatePresence>
          {selectedDocId && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-b border-surface-200 dark:border-surface-700"
            >
              <div className="px-4 py-1.5 bg-brand-50/50 dark:bg-brand-950/20 flex items-center gap-2">
                <FileText size={12} className="text-brand-500" />
                <span className="text-[11px] text-brand-700 dark:text-brand-300">
                  Filtering: <span className="font-semibold">{selectedDoc?.source_file}</span>
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Pipeline trace bar */}
        <AnimatePresence>
          {pipelineStep && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0"
            >
              <div className="px-6 py-2">
                <PipelineTrace activeStep={pipelineStep} metrics={lastResponse?.metrics ?? null} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {!hasMessages && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full pb-24">
              <div className="w-14 h-14 rounded-2xl bg-brand-600/10 dark:bg-brand-500/10 flex items-center justify-center mb-5">
                <MessageSquare size={24} className="text-brand-600 dark:text-brand-400" />
              </div>
              <h2 className="text-base font-semibold text-surface-800 dark:text-surface-200 mb-1">
                Ask your documents
              </h2>
              <p className="text-xs text-surface-400 text-center max-w-xs leading-relaxed mb-6">
                Every answer is grounded in your uploaded documents with full
                source citations and a confidence score.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-md">
                {STARTERS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    className="px-3 py-1.5 text-xs rounded-full border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 text-surface-600 dark:text-surface-400 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950/30 transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeConv?.messages.map((msg, i) => (
            <MessageBubble
              key={msg.id ?? i}
              message={msg}
              onFeedback={(sentiment) => handleFeedback(i, sentiment)}
            />
          ))}

          {isLoading && <StreamingBubble text="" />}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
          <ChatInput
            onSend={handleSend}
            onStop={() => setIsLoading(false)}
            isStreaming={isLoading}
          />
        </div>
      </div>

      {/* Right: debug panel */}
      <AnimatePresence>
        {debugPanelOpen && lastResponse && (
          <DebugPanel response={lastResponse} onClose={toggleDebugPanel} />
        )}
      </AnimatePresence>
    </div>
  )
}
