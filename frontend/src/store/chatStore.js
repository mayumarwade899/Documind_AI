import { create } from 'zustand'
import { persist } from 'zustand/middleware'

function generateId() {
  return Math.random().toString(36).slice(2, 10)
}

export const useChatStore = create(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,

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
        set({ conversations: [], activeConversationId: null })
      },
    }),
    {
      name: 'documind-chat',
      partialize: (s) => ({
        conversations: s.conversations.slice(0, 50), // keep last 50
        activeConversationId: s.activeConversationId,
      }),
    }
  )
)
