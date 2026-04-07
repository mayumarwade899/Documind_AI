import { useNavigate } from 'react-router-dom'
import { Home } from 'lucide-react'

export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <p className="text-7xl font-bold text-surface-200 dark:text-surface-800 mb-4 select-none">404</p>
      <h1 className="text-lg font-semibold text-surface-800 dark:text-surface-200 mb-2">Page not found</h1>
      <p className="text-sm text-surface-400 mb-6">The page you're looking for doesn't exist.</p>
      <button
        onClick={() => navigate('/dashboard')}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors"
      >
        <Home size={15} />
        Back to dashboard
      </button>
    </div>
  )
}
