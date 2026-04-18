import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Trash2, MessageSquare, FileText, ChevronDown, X, Upload, Download, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { clearChatHistory } from '../services/queryService.js'

import { useChatStore } from '../store/chatStore.js'
import { queryRAG, streamQuery, submitFeedback } from '../services/queryService.js'
import { getDocuments } from '../services/ingestService.js'

import { ConversationList } from '../features/chat/ConversationList.jsx'
import { MessageBubble, StreamingBubble } from '../features/chat/MessageBubble.jsx'
import { ChatInput } from '../features/chat/ChatInput.jsx'
import { PipelineTrace } from '../features/debug/PipelineTrace.jsx'

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
  const location = useLocation()

  const {
    conversations,
    activeConversationId,
    newConversation,
    addMessage,
    updateLastMessage,
    setActiveConversation,
    getSessionId,
    syncWithBackend,
    clearAll,
  } = useChatStore()

  const [lastResponse, setLastResponse] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(null)

  const [documents, setDocuments] = useState([])
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [docDropdownOpen, setDocDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  const messagesEndRef = useRef(null)
  const innerListRef = useRef(null)
  const scrollContainerRef = useRef(null)
  const activeConv =
    conversations.find(
      (c) => c.id === (conversationId ?? activeConversationId)
    ) ?? null

  const hasMessages = (activeConv?.messages?.length ?? 0) > 0

  useEffect(() => {
    if (conversationId) setActiveConversation(conversationId)
    syncWithBackend()

    if (location.state?.document_id) {
      setSelectedDocId(location.state.document_id)
    } else {
      setSelectedDocId(null)
    }
  }, [conversationId])

  // Missing Conversation Guard: If we are on a chat ID that no longer exists,
  // sync the URL with the store's calculated fallback.
  useEffect(() => {
    if (conversationId && conversations.length > 0 && !conversations.some(c => c.id === conversationId)) {
      if (activeConversationId) {
        navigate(`/chat/${activeConversationId}`, { replace: true })
      } else {
        navigate('/chat', { replace: true })
      }
    }
  }, [conversationId, conversations, activeConversationId, navigate])

  const isStreamingActive = activeConv?.messages?.[activeConv?.messages?.length - 1]?._streaming;
  useLayoutEffect(() => {
    const scrollEl = scrollContainerRef.current;
    const innerEl = innerListRef.current;
    if (!scrollEl || !innerEl) return;
    const observer = new ResizeObserver(() => {
      if (isStreamingActive || isLoading) {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }
    });
    observer.observe(innerEl);
    observer.observe(scrollEl);
    scrollEl.scrollTop = scrollEl.scrollHeight;

    return () => observer.disconnect();
  }, [activeConversationId, isStreamingActive, isLoading]);

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

  const selectedDoc = documents.find((d) => d.document_id === selectedDocId)

  const pipelineTimers = useRef([])

  function clearPipelineTimers() {
    pipelineTimers.current.forEach(clearTimeout)
    pipelineTimers.current = []
  }

  async function handleSend(query, options = {}) {
    if (!selectedDocId) {
      toast.error('Please select a document from the dropdown before asking a question.')
      return
    }

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
    addMessage(convId, { role: 'assistant', content: '', _streaming: true })

    let streamingText = ''
    let streamingRewrite = null

    try {
      const reader = await streamQuery({
        query,
        use_query_rewriting: options.use_query_rewriting ?? true,
        use_multi_query: options.use_multi_query ?? true,
        verify_answer: false,
        document_id: selectedDocId,
        session_id: getSessionId(),
        history: activeConv?.messages.slice(-5).map(m => ({
          role: m.role,
          content: m.content,
        })) || [],
      })

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          let event
          try { event = JSON.parse(raw) } catch { continue }

          if (event.type === 'meta') {
            if (event.rewritten_query) streamingRewrite = event.rewritten_query
            if (event.step) setPipelineStep(event.step)

          } else if (event.type === 'chunk') {
            streamingText += event.text
            updateLastMessage(convId, {
              content: streamingText,
              rewrittenQuery: streamingRewrite,
              _streaming: true,
            })

          } else if (event.type === 'done') {
            setPipelineStep('done')
            updateLastMessage(convId, {
              content: streamingText,
              sources: event.sources ?? [],
              metrics: event.metrics ?? null,
              verification: null,
              rewrittenQuery: event.rewritten_query ?? streamingRewrite,
              success: true,
              _streaming: false,
            })
            setLastResponse({ answer: streamingText, sources: event.sources, metrics: event.metrics })

          } else if (event.type === 'error') {
            throw new Error(event.message)
          }
        }
      }
    } catch (err) {
      clearPipelineTimers()
      setPipelineStep(null)
      const msg = err.message ?? 'Query failed. Please try again.'
      toast.error(msg)
      updateLastMessage(convId, {
        content: `Unable to process your query: ${msg}`,
        success: false,
        _streaming: false,
      })
    } finally {
      setIsLoading(false)
      setTimeout(() => setPipelineStep(null), 2000)
    }
  }

  async function handleFeedback(messageIndex, sentiment, commentText = null) {
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
        comment: commentText,
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

  const exportChat = () => {
    if (!activeConv || activeConv.messages.length === 0) return
    const text = activeConv.messages.map(m => `### ${m.role === 'user' ? 'User' : 'Assistant'}\n${m.content}`).join('\n\n')
    const blob = new Blob([text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${activeConv.title || 'chat_export'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClearHistory = async () => {
    if (!window.confirm('Are you sure you want to clear all chat history from this session? This will also wipe server records.')) return

    try {
      const sid = getSessionId()
      await clearChatHistory(sid)
      clearAll()
      navigate('/chat')
      toast.success('History cleared')
    } catch (err) {
      toast.error('Failed to clear server history')
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-48 shrink-0 border-r border-surface-200 dark:border-surface-700 flex flex-col bg-white dark:bg-surface-900">
        <div className="flex items-center justify-between h-11 px-2.5 border-b border-surface-200 dark:border-surface-700 shrink-0">
          <span className="text-xs font-semibold uppercase tracking-wide text-surface-400">
            History
          </span>
          <button
            onClick={handleClearHistory}
            className="p-1 rounded-md text-surface-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
            title="Clear all history"
          >
            <Trash2 size={13} />
          </button>
        </div>
        <ConversationList />
      </div>
      <div className="flex-1 flex flex-col min-w-0 bg-surface-50 dark:bg-surface-950">
        <div className="flex items-center justify-between h-11 px-4 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
          <span className="text-sm font-medium text-surface-700 dark:text-surface-300 truncate max-w-sm">
            {activeConv?.title ?? 'Chat'}
          </span>
          <div className="flex items-center gap-1.5">
            {activeConv?.messages?.length > 0 && (
              <button
                onClick={exportChat}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-850 text-surface-500 dark:text-surface-400 hover:border-surface-300 dark:hover:border-surface-600 transition-all"
                title="Export as Markdown"
              >
                <Download size={12} />
                <span>Export</span>
              </button>
            )}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDocDropdownOpen(!docDropdownOpen)}
                className={`
                  flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border transition-all
                  ${selectedDocId
                    ? 'border-brand-400 dark:border-brand-500 bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300'
                    : 'border-amber-400 dark:border-amber-500 bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 animate-pulse'
                  }
                `}
                id="document-selector-btn"
              >
                <FileText size={12} />
                <span className="max-w-[120px] truncate">
                  {selectedDoc ? selectedDoc.source_file : 'Select a document'}
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
                      {documents.map((doc) => (
                        <button
                          key={doc.document_id}
                          onClick={() => {
                            setSelectedDocId(doc.document_id)
                            setDocDropdownOpen(false)
                          }}
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
                          {selectedDocId === doc.document_id && (
                            <span className="ml-auto text-[10px] text-brand-500 font-semibold shrink-0">Active</span>
                          )}
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

            <button
              onClick={() => navigate('/documents')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-brand-500 dark:border-brand-600 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950/40 transition-all"
            >
              <Upload size={12} />
              Upload docs
            </button>
          </div>
        </div>

        <AnimatePresence>
          {selectedDocId && (
            <motion.div
              key="doc-active"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-b border-surface-200 dark:border-surface-700"
            >
              <div className="px-4 py-1.5 bg-brand-50/50 dark:bg-brand-950/20 flex items-center gap-2">
                <FileText size={12} className="text-brand-500" />
                <span className="text-[11px] text-brand-700 dark:text-brand-300">
                  Filtering to: <span className="font-semibold">{selectedDoc?.source_file}</span>
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
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
        <div className="flex-1 overflow-y-auto px-6 py-5" ref={scrollContainerRef}>
          <div ref={innerListRef} className="flex flex-col gap-5 h-max">
            {!hasMessages && !isLoading && (
              <div className="flex flex-col items-center justify-center h-full pb-24">
                <div className="w-14 h-14 rounded-2xl bg-brand-600/10 dark:bg-brand-500/10 flex items-center justify-center mb-5">
                  <MessageSquare size={24} className="text-brand-600 dark:text-brand-400" />
                </div>
                <h2 className="text-base font-semibold text-surface-800 dark:text-surface-200 mb-1">
                  Ask your documents
                </h2>
                <p className="text-xs text-surface-400 text-center max-w-xs leading-relaxed mb-6">
                  {selectedDocId
                    ? `Asking questions about "${selectedDoc?.source_file}"`
                    : 'Select a document from the dropdown to get started.'}
                </p>
                {selectedDocId && (
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
                )}
              </div>
            )}

            {activeConv?.messages.map((msg, i) => (
              msg._streaming
                ? <StreamingBubble
                  key={msg.id ?? i}
                  text={msg.content}
                  queryRewrite={msg.rewrittenQuery}
                />
                : <MessageBubble
                  key={msg.id ?? i}
                  message={msg}
                  onFeedback={(sentiment, commentText) => handleFeedback(i, sentiment, commentText)}
                />
            ))}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 shrink-0">
          {!selectedDocId && (
            <div className="flex items-center gap-2 mb-2 px-1">
              <AlertCircle size={13} className="text-amber-500 shrink-0" />
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Select a document above to enable the chat input
              </p>
            </div>
          )}
          <ChatInput
            onSend={handleSend}
            onStop={() => setIsLoading(false)}
            isStreaming={isLoading}
            disabled={!selectedDocId}
          />
        </div>
      </div>

    </div>
  )
}
