import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useUIStore = create(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      debugPanelOpen: false,

      toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      toggleDebugPanel: () => set((s) => ({ debugPanelOpen: !s.debugPanelOpen })),
      setDebugPanelOpen: (v) => set({ debugPanelOpen: v }),
    }),
    { name: 'documind-ui' }
  )
)
