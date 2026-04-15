import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getChatHistory } from '../services/queryService.js'

function generateId() {
  return Math.random().toString(36).slice(2, 10)
}

export const useChatStore = create(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      sessionId: null,

      getSessionId() {
        let sid = get().sessionId
        if (!sid) {
          sid = `sess_${generateId()}_${Date.now()}`
          set({ sessionId: sid })
        }
        return sid
      },

      newConversation() {
        const id = generateId()
        const conv = {
          id,
          title: 'New conversation',
          messages: [],
          createdAt: new Date().toISOString(),
          lastActivity: new Date().toISOString(),
        }
        set((s) => ({
          conversations: [conv, ...s.conversations],
          activeConversationId: id,
        }))
        return id
      },

      setActiveConversation(id) {
        set({ activeConversationId: id })
      },

      deleteConversation(id) {
        set((s) => ({
          conversations: s.conversations.filter((c) => c.id !== id),
          activeConversationId:
            s.activeConversationId === id
              ? s.conversations.find((c) => c.id !== id)?.id ?? null
              : s.activeConversationId,
        }))
      },

      addMessage(convId, message) {
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === convId
              ? {
                ...c,
                messages: [...c.messages, { ...message, id: generateId(), timestamp: new Date().toISOString() }],
                lastActivity: new Date().toISOString(),
                title: c.title === 'New conversation' && message.role === 'user'
                  ? message.content.slice(0, 42) + (message.content.length > 42 ? '…' : '')
                  : c.title,
              }
              : c
          ),
        }))
      },

      updateLastMessage(convId, updates) {
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === convId
              ? {
                ...c,
                messages: c.messages.map((m, i) =>
                  i === c.messages.length - 1 ? { ...m, ...updates } : m
                ),
              }
              : c
          ),
        }))
      },

      getActiveConversation() {
        const { conversations, activeConversationId } = get()
        return conversations.find((c) => c.id === activeConversationId) ?? null
      },

      clearAll() {
        set({ conversations: [], activeConversationId: null, sessionId: null })
      },

      async syncWithBackend() {
        const sid = get().getSessionId()
        try {
          const history = await getChatHistory(sid)
          if (!history || history.length === 0) return

          set((s) => {
            const hasSyncedConv = s.conversations.some(c => c.id === 'synced_session')

            const messages = history.map((item, idx) => ([
              {
                id: `u_${idx}`,
                role: 'user',
                content: item.query,
                timestamp: item.timestamp,
              },
              {
                id: `a_${idx}`,
                role: 'assistant',
                content: item.answer,
                sources: item.sources,
                verification: item.verification,
                metrics: item.metrics,
                rewrittenQuery: item.rewritten_query,
                timestamp: item.timestamp,
              }
            ])).flat()

            if (hasSyncedConv) {
              return {
                conversations: s.conversations.map(c =>
                  c.id === 'synced_session' ? { ...c, messages, lastActivity: new Date().toISOString() } : c
                )
              }
            } else {
              const syncConv = {
                id: 'synced_session',
                title: 'Synced History',
                messages,
                createdAt: history[0].timestamp,
                lastActivity: new Date().toISOString(),
              }
              return { conversations: [syncConv, ...s.conversations] }
            }
          })
        } catch (err) {
          console.error('Failed to sync history:', err)
        }
      },
    }),
    {
      name: 'documind-chat',
      partialize: (s) => ({
        conversations: s.conversations.slice(0, 50),
        activeConversationId: s.activeConversationId,
        sessionId: s.sessionId,
      }),
    }
  )
)
