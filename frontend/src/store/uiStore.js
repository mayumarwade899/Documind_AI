import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useUIStore = create(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      isEvaluating: false,
      lastEvalResult: null,

      toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      setEvaluating: (v) => set({ isEvaluating: v }),
      setLastEvalResult: (res) => set({ lastEvalResult: res }),
    }),
    { 
      name: 'documind-ui',
      partialize: (s) => ({
        theme: s.theme,
        sidebarCollapsed: s.sidebarCollapsed
      })
    }
  )
)
