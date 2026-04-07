import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Trash2, MessageSquare, Search } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useChatStore } from '../../store/chatStore.js'
import { timeAgo } from '../../utils/format.js'
import { cn } from '../../utils/cn.js'

export function ConversationList() {
  const { conversations, activeConversationId, deleteConversation, setActiveConversation } = useChatStore()
  const navigate = useNavigate()
  const { conversationId } = useParams()
  const [search, setSearch] = useState('')

  function select(id) {
    setActiveConversation(id)
    navigate(`/chat/${id}`)
  }

  const filtered = conversations.filter(c => c.title.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="px-3 py-2 border-b border-surface-100 dark:border-surface-800 shrink-0">
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Search chats..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-8 pr-2 py-1.5 text-xs bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-md focus:outline-none focus:border-brand-500 transition-colors"
          />
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto py-1">
        {!filtered.length ? (
          <div className="flex flex-col items-center justify-center h-40 text-center px-4">
            <MessageSquare size={22} className="text-surface-300 dark:text-surface-600 mb-2" />
            <p className="text-xs text-surface-400">{search ? 'No matches' : 'No conversations yet'}</p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {filtered.map((conv) => {
              const isActive = conv.id === (conversationId ?? activeConversationId)
              return (
                <motion.div
                  key={conv.id}
                  layout
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  <div
                    onClick={() => select(conv.id)}
                    className={cn(
                      'group relative mx-2 my-0.5 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
                      isActive
                        ? 'bg-brand-50 dark:bg-brand-950/60'
                        : 'hover:bg-surface-100 dark:hover:bg-surface-800'
                    )}
                  >
                    <p className={cn(
                      'text-xs font-medium truncate pr-5',
                      isActive
                        ? 'text-brand-700 dark:text-brand-300'
                        : 'text-surface-700 dark:text-surface-300'
                    )}>
                      {conv.title}
                    </p>
                    <div className="flex items-center justify-between mt-0.5">
                      <p className="text-[10px] text-surface-400">
                        {conv.messages.length} msg{conv.messages.length !== 1 ? 's' : ''} · {timeAgo(conv.lastActivity)}
                      </p>
                    </div>

                    <button
                      onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id) }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/40 text-surface-400 hover:text-red-500 transition-all"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
