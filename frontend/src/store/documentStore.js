import { create } from 'zustand'

export const useDocumentStore = create((set, get) => ({
  documents: [],       // { id, filename, chunks, pages, status, ingestedAt }
  uploadQueue: [],     // { id, file, status, progress, result, error }

  setDocuments(docs) {
    set({ documents: docs })
  },

  addToQueue(item) {
    set((s) => ({ uploadQueue: [item, ...s.uploadQueue] }))
  },

  updateQueueItem(id, updates) {
    set((s) => ({
      uploadQueue: s.uploadQueue.map((i) => (i.id === id ? { ...i, ...updates } : i)),
    }))
  },

  clearQueue() {
    set({ uploadQueue: [] })
  },

  removeFromQueue(id) {
    set((s) => ({ uploadQueue: s.uploadQueue.filter((i) => i.id !== id) }))
  },
}))
