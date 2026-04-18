import { NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, MessageSquare, FileText, BarChart3,
  FlaskConical, ChevronLeft, ChevronRight, Sun, Moon,
  Zap, Plus
} from 'lucide-react'
import { cn } from '../../utils/cn.js'
import { useUIStore } from '../../store/uiStore.js'
import { useChatStore } from '../../store/chatStore.js'
import { Tooltip } from '../ui/index.jsx'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/evaluation', icon: FlaskConical, label: 'Evaluation' },
  { to: '/monitoring', icon: BarChart3, label: 'Monitoring' },
]

export default function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed, theme, toggleTheme } = useUIStore()
  const { newConversation } = useChatStore()
  const navigate = useNavigate()

  function handleNewChat() {
    const id = newConversation()
    navigate(`/chat/${id}`)
  }

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarCollapsed ? 60 : 190 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="flex flex-col h-full bg-white dark:bg-surface-900 border-r border-surface-200 dark:border-surface-800 shrink-0 overflow-hidden"
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-2.5 border-b border-surface-200 dark:border-surface-800 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center shrink-0 shadow-glow-sm">
            <Zap size={14} className="text-white" />
          </div>
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.15 }}
                className="font-display font-semibold text-sm text-surface-900 dark:text-white tracking-tight whitespace-nowrap"
              >
                DocuMind
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* New chat button */}
      <div className="px-2 py-3 shrink-0">
        {sidebarCollapsed ? (
          <Tooltip content="New chat" side="right">
            <button onClick={handleNewChat} className="w-full flex items-center justify-center h-8 rounded-lg bg-brand-600 hover:bg-brand-700 text-white transition-colors">
              <Plus size={15} />
            </button>
          </Tooltip>
        ) : (
          <button onClick={handleNewChat} className="w-full flex items-center gap-2 h-8 px-3 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium transition-colors">
            <Plus size={14} />
            <span>New chat</span>
          </button>
        )}
      </div>

      {/* Nav links */}
      <nav className={cn('flex-1 px-2 space-y-1 overflow-y-auto scrollbar-none', sidebarCollapsed && 'flex flex-col items-center')}
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {NAV.map(({ to, icon: Icon, label }) => (
          sidebarCollapsed ? (
            <Tooltip key={to} content={label} side="right">
              <NavLink
                to={to}
                className={({ isActive }) => cn(
                  'flex items-center justify-center w-10 h-10 rounded-lg transition-colors',
                  isActive
                    ? 'bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-400'
                    : 'text-surface-500 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-700 dark:hover:text-surface-300'
                )}
              >
                <Icon size={18} />
              </NavLink>
            </Tooltip>
          ) : (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => cn(
                'flex items-center gap-2 h-9 px-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-400 font-medium'
                  : 'text-surface-500 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-700 dark:hover:text-surface-300'
              )}
            >
              <Icon size={16} className="shrink-0" />
              <span className="truncate">{label}</span>
            </NavLink>
          )
        ))}
      </nav>

      {/* Bottom controls */}
      <div className="px-2 py-3 border-t border-surface-200 dark:border-surface-800 shrink-0 space-y-1">
        {/* Theme toggle */}
        {sidebarCollapsed ? (
          <Tooltip content={theme === 'dark' ? 'Light mode' : 'Dark mode'} side="right">
            <button onClick={toggleTheme} className="w-full flex items-center justify-center h-9 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-600 dark:hover:text-surface-300 transition-colors">
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </Tooltip>
        ) : (
          <button onClick={toggleTheme} className="w-full flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-sm text-surface-500 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-700 dark:hover:text-surface-300 transition-colors">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
          </button>
        )}

        {/* Collapse toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="w-full flex items-center justify-center h-9 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : (
            <span className="flex items-center gap-2 text-sm px-3 w-full">
              <ChevronLeft size={16} />
              <span>Collapse</span>
            </span>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
