import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { useEffect } from 'react'

import Layout from './components/layout/Layout.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import DocumentsPage from './pages/DocumentsPage.jsx'
import EvaluationPage from './pages/EvaluationPage.jsx'
import MonitoringPage from './pages/MonitoringPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import { ErrorBoundary } from './components/ui/ErrorBoundary.jsx'
import { useUIStore } from './store/uiStore.js'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  const { theme } = useUIStore()

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') root.classList.add('dark')
    else root.classList.remove('dark')
  }, [theme])

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/chat/:conversationId" element={<ChatPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/evaluation" element={<EvaluationPage />} />
              <Route path="/monitoring" element={<MonitoringPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          className: '',
          style: {
            background: theme === 'dark' ? '#1c1c21' : '#ffffff',
            color: theme === 'dark' ? '#ffffff' : '#101013',
            border: theme === 'dark' ? '1px solid #3a3a42' : '1px solid #e4e4e8',
            borderRadius: '10px',
            fontSize: '13px',
            padding: '10px 14px',
          },
          success: { iconTheme: { primary: '#7c4dff', secondary: '#fff' } },
        }}
      />
    </QueryClientProvider>
  )
}
