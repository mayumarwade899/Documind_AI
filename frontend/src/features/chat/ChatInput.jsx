import { useState, useRef, useEffect } from 'react'
import { Send, Square, Sliders, ChevronDown } from 'lucide-react'
import { cn } from '../../utils/cn.js'

export function ChatInput({ onSend, onStop, isStreaming, disabled }) {
  const [value, setValue]         = useState('')
  const [showOpts, setShowOpts]   = useState(false)
  const [useRewrite, setUseRewrite]   = useState(true)
  const [useMultiQuery, setUseMultiQuery] = useState(true)
  const [verifyAnswer, setVerifyAnswer]   = useState(true)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }, [value])

  function submit() {
    const q = value.trim()
    if (!q || isStreaming) return
    onSend(q, { use_query_rewriting: useRewrite, use_multi_query: useMultiQuery, verify_answer: verifyAnswer })
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  return (
    <div className="relative">
      {/* Options panel */}
      {showOpts && (
        <div className="absolute bottom-full left-0 right-0 mb-2 p-3 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-2">Pipeline options</p>
          <div className="space-y-2">
            {[
              { label: 'Query rewriting', value: useRewrite, set: setUseRewrite, desc: 'Improves retrieval with LLM-rewritten query' },
              { label: 'Multi-query',     value: useMultiQuery, set: setUseMultiQuery, desc: 'Generates 3 query variants for broader retrieval' },
              { label: 'Verify answer',   value: verifyAnswer, set: setVerifyAnswer, desc: 'Cross-checks answer claims against source chunks' },
            ].map(opt => (
              <label key={opt.label} className="flex items-start gap-3 cursor-pointer group">
                <div className="mt-0.5">
                  <div
                    onClick={() => opt.set(!opt.value)}
                    className={cn(
                      'w-8 h-4 rounded-full transition-colors cursor-pointer relative',
                      opt.value ? 'bg-brand-600' : 'bg-surface-300 dark:bg-surface-600'
                    )}
                  >
                    <div className={cn(
                      'absolute top-0.5 w-3 h-3 bg-white rounded-full shadow-sm transition-transform',
                      opt.value ? 'translate-x-4' : 'translate-x-0.5'
                    )} />
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-surface-700 dark:text-surface-300">{opt.label}</p>
                  <p className="text-[10px] text-surface-400 mt-0.5">{opt.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="flex items-end gap-2 p-3 bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card focus-within:border-brand-400 dark:focus-within:border-brand-500 transition-colors">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask anything about your documents…"
          disabled={disabled || isStreaming}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm text-surface-900 dark:text-white placeholder:text-surface-400 focus:outline-none min-h-[24px] max-h-40 leading-6 disabled:opacity-50"
        />

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => setShowOpts(!showOpts)}
            className={cn(
              'p-1.5 rounded-lg transition-colors',
              showOpts
                ? 'bg-brand-100 dark:bg-brand-900 text-brand-600 dark:text-brand-400'
                : 'text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-600'
            )}
          >
            <Sliders size={15} />
          </button>

          {isStreaming ? (
            <button
              onClick={onStop}
              className="p-1.5 rounded-lg bg-red-100 dark:bg-red-900/40 text-red-600 hover:bg-red-200 dark:hover:bg-red-900 transition-colors"
            >
              <Square size={15} />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!value.trim() || disabled}
              className={cn(
                'p-1.5 rounded-lg transition-all',
                value.trim()
                  ? 'bg-brand-600 hover:bg-brand-700 text-white shadow-glow-sm'
                  : 'bg-surface-100 dark:bg-surface-800 text-surface-300 dark:text-surface-600 cursor-not-allowed'
              )}
            >
              <Send size={15} />
            </button>
          )}
        </div>
      </div>

      <p className="text-center text-[10px] text-surface-300 dark:text-surface-600 mt-1.5">
        Enter to send · Shift+Enter for new line · answers grounded in your documents
      </p>
    </div>
  )
}
