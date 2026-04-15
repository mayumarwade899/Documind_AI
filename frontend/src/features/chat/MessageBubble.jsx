import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { ThumbsUp, ThumbsDown, Copy, Check, Bot, User } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { CitationCard } from './CitationCard.jsx'
import { ConfidenceBar, InlineMeta } from '../../components/shared/index.jsx'
import { cn } from '../../utils/cn.js'
import { useUIStore } from '../../store/uiStore.js'
import toast from 'react-hot-toast'

function CodeBlock({ language, children }) {
  const [copied, setCopied] = useState(false)
  const { theme } = useUIStore()

  function copy() {
    navigator.clipboard.writeText(String(children))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden border border-surface-200 dark:border-surface-700">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-100 dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <span className="text-[10px] font-mono text-surface-400">{language || 'code'}</span>
        <button onClick={copy} className="flex items-center gap-1 text-[10px] text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors">
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <SyntaxHighlighter
        style={theme === 'dark' ? oneDark : oneLight}
        language={language}
        PreTag="div"
        customStyle={{ margin: 0, borderRadius: 0, fontSize: '12px', background: 'transparent' }}
      >
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    </div>
  )
}

const components = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '')
    return !inline && match
      ? <CodeBlock language={match[1]}>{children}</CodeBlock>
      : <code className="font-mono text-xs bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 rounded text-brand-700 dark:text-brand-400" {...props}>{children}</code>
  }
}

export function MessageBubble({ message, onFeedback }) {
  const { role, content, sources, verification, metrics, feedback } = message
  const isAssistant = role === 'assistant'
  const [copied, setCopied] = useState(false)
  const [showCommentBox, setShowCommentBox] = useState(false)
  const [commentText, setCommentText] = useState('')

  function copyAnswer() {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast.success('Copied to clipboard')
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn('flex gap-3', isAssistant ? 'flex-row' : 'flex-row-reverse')}
    >
      <div className={cn(
        'w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 text-white text-xs font-semibold',
        isAssistant ? 'bg-brand-600' : 'bg-surface-700 dark:bg-surface-600'
      )}>
        {isAssistant ? <Bot size={14} /> : <User size={14} />}
      </div>

      <div className={cn(
        'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
        isAssistant
          ? 'bg-white dark:bg-surface-850 border border-surface-200 dark:border-surface-700 shadow-card'
          : 'bg-brand-600 text-white rounded-tr-sm'
      )}>
        {isAssistant ? (
          <>
            <div className="prose-chat text-surface-800 dark:text-surface-200">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {content}
              </ReactMarkdown>
            </div>

            {metrics && (
              <div className="mt-3 pt-2.5 border-t border-surface-100 dark:border-surface-700/60">
                <InlineMeta metrics={metrics} />
              </div>
            )}

            {verification && (
              <ConfidenceBar ratio={verification.support_ratio} hasCitations={verification.has_citations} />
            )}

            {sources?.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <p className="text-[10px] font-semibold text-surface-400 uppercase tracking-wide mb-2">Sources</p>
                {sources.map((s, i) => <CitationCard key={i} source={s} index={i + 1} />)}
              </div>
            )}

            <div className="mt-3 flex items-center gap-1.5">
              <button
                onClick={copyAnswer}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
              >
                {copied ? <Check size={11} /> : <Copy size={11} />}
                {copied ? 'Copied' : 'Copy'}
              </button>
              <div className="ml-auto flex items-center gap-1">
                <button
                  onClick={() => onFeedback?.('positive')}
                  className={cn(
                    'flex items-center gap-1 px-2 py-1 rounded-md text-[10px] transition-colors',
                    feedback === 'positive'
                      ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-600'
                      : 'text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-emerald-600'
                  )}
                >
                  <ThumbsUp size={11} />
                </button>
                <button
                  onClick={() => {
                    if (feedback === 'negative') return
                    setShowCommentBox(true)
                  }}
                  className={cn(
                    'flex items-center gap-1 px-2 py-1 rounded-md text-[10px] transition-colors',
                    feedback === 'negative'
                      ? 'bg-red-100 dark:bg-red-950 text-red-600'
                      : (showCommentBox ? 'bg-surface-200 dark:bg-surface-700 text-red-500' : 'text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-red-500')
                  )}
                >
                  <ThumbsDown size={11} />
                </button>
              </div>
            </div>

            <AnimatePresence>
              {showCommentBox && feedback !== 'negative' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3 overflow-hidden"
                >
                  <div className="p-3 bg-surface-50 dark:bg-surface-900/50 rounded-lg border border-surface-200 dark:border-surface-700">
                    <p className="text-[10px] font-semibold text-surface-500 mb-2">What went wrong?</p>
                    <textarea
                      value={commentText}
                      onChange={e => setCommentText(e.target.value)}
                      placeholder="Optional feedback..."
                      className="w-full text-xs p-2 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-md resize-none h-16 focus:outline-none focus:border-brand-500 mb-2 text-surface-700 dark:text-surface-300 placeholder:text-surface-400"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => {
                          setShowCommentBox(false)
                          setCommentText('')
                        }}
                        className="px-2 py-1 text-[10px] text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => {
                          onFeedback?.('negative', commentText)
                          setShowCommentBox(false)
                        }}
                        className="px-3 py-1 bg-red-500 hover:bg-red-600 text-white rounded text-[10px] font-semibold transition-colors disabled:opacity-50"
                      >
                        Submit
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        ) : (
          <p className="whitespace-pre-wrap">{content}</p>
        )}
      </div>
    </motion.div>
  )
}

export function StreamingBubble({ text, queryRewrite }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3"
    >
      <div className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center shrink-0 mt-1 animate-pulse-soft">
        <Bot size={14} className="text-white" />
      </div>
      <div className="max-w-[80%] rounded-2xl px-4 py-3 text-sm bg-white dark:bg-surface-850 border border-surface-200 dark:border-surface-700 shadow-card">
        {queryRewrite && (
          <div className="mb-2 pb-2 border-b border-surface-100 dark:border-surface-700">
            <p className="text-[10px] text-surface-400 uppercase font-semibold tracking-wide mb-1">Query rewritten to</p>
            <p className="text-xs text-brand-600 dark:text-brand-400 italic">{queryRewrite}</p>
          </div>
        )}
        {text ? (
          <div className="prose-chat text-surface-800 dark:text-surface-200">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{text}</ReactMarkdown>
            <span className="inline-block w-0.5 h-4 bg-brand-500 ml-0.5 animate-stream-cursor" />
          </div>
        ) : (
          <div className="flex items-center gap-1.5 h-5">
            {[0, 1, 2].map(i => (
              <div
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-thinking"
                style={{ animationDelay: `${i * 0.16}s` }}
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}
