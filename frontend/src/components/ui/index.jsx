import { cn } from '../../utils/cn.js'
import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

/* ─── Button ─────────────────────────────────────────────── */
export function Button({ variant = 'primary', size = 'md', className, children, ...props }) {
  const base = 'inline-flex items-center gap-2 font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed select-none'

  const variants = {
    primary:   'bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white shadow-sm',
    secondary: 'bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-200 border border-surface-200 dark:border-surface-700',
    ghost:     'hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-600 dark:text-surface-400',
    danger:    'bg-red-600 hover:bg-red-700 text-white',
    outline:   'border border-brand-600 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950',
  }

  const sizes = {
    xs: 'px-2.5 py-1 text-xs',
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  }

  return (
    <button className={cn(base, variants[variant], sizes[size], className)} {...props}>
      {children}
    </button>
  )
}

/* ─── Badge ──────────────────────────────────────────────── */
export function Badge({ variant = 'default', size = 'sm', className, children }) {
  const variants = {
    default:  'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400',
    brand:    'bg-brand-100 dark:bg-brand-950 text-brand-700 dark:text-brand-300',
    success:  'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400',
    warning:  'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400',
    danger:   'bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-400',
    info:     'bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-400',
    outline:  'border border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400',
  }
  const sizes = {
    xs: 'px-1.5 py-0.5 text-[10px]',
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
  }
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-md font-medium', variants[variant], sizes[size], className)}>
      {children}
    </span>
  )
}

/* ─── Spinner ────────────────────────────────────────────── */
export function Spinner({ size = 'md', className }) {
  const sizes = { xs: 'w-3 h-3', sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-7 h-7' }
  return (
    <div className={cn('rounded-full border-2 border-current border-t-transparent animate-spin opacity-70', sizes[size], className)} />
  )
}

/* ─── Card ───────────────────────────────────────────────── */
export function Card({ className, children, hover = false, ...props }) {
  return (
    <div
      className={cn(
        'bg-white dark:bg-surface-850 rounded-xl border border-surface-200 dark:border-surface-700 shadow-card',
        hover && 'transition-shadow duration-200 hover:shadow-card-hover cursor-pointer',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

/* ─── Progress ───────────────────────────────────────────── */
export function Progress({ value = 0, max = 100, variant = 'brand', className, showLabel = false }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const colors = {
    brand:   'bg-brand-500',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger:  'bg-red-500',
  }
  return (
    <div className={cn('space-y-1', className)}>
      {showLabel && (
        <div className="flex justify-between text-xs text-surface-500">
          <span>{pct.toFixed(0)}%</span>
        </div>
      )}
      <div className="h-1.5 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', colors[variant])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

/* ─── Tabs ───────────────────────────────────────────────── */
export function Tabs({ tabs, active, onChange, className }) {
  return (
    <div className={cn('flex gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-lg', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-150',
            active === tab.id
              ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
              : 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300'
          )}
        >
          {tab.icon && <span className="w-3.5 h-3.5">{tab.icon}</span>}
          {tab.label}
          {tab.count != null && (
            <span className={cn(
              'ml-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold',
              active === tab.id ? 'bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300' : 'bg-surface-200 dark:bg-surface-700 text-surface-500'
            )}>
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

/* ─── Modal ──────────────────────────────────────────────── */
export function Modal({ open, onClose, title, children, size = 'md', className }) {
  const overlayRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handle = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handle)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handle)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  const sizes = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl', full: 'max-w-[95vw]' }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className={cn(
        'relative w-full bg-white dark:bg-surface-850 rounded-2xl shadow-2xl border border-surface-200 dark:border-surface-700 animate-slide-up',
        sizes[size], className
      )}>
        {title && (
          <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200 dark:border-surface-700">
            <h2 className="text-base font-semibold text-surface-900 dark:text-white">{title}</h2>
            <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors">
              <X size={16} />
            </button>
          </div>
        )}
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

/* ─── Tooltip ────────────────────────────────────────────── */
export function Tooltip({ content, children, side = 'top' }) {
  return (
    <div className="relative group">
      {children}
      <div className={cn(
        'pointer-events-none absolute z-50 px-2 py-1 text-xs font-medium text-white bg-surface-800 dark:bg-surface-700 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-150',
        side === 'top'    && 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
        side === 'bottom' && 'top-full left-1/2 -translate-x-1/2 mt-1.5',
        side === 'left'   && 'right-full top-1/2 -translate-y-1/2 mr-1.5',
        side === 'right'  && 'left-full top-1/2 -translate-y-1/2 ml-1.5',
      )}>
        {content}
      </div>
    </div>
  )
}

/* ─── EmptyState ─────────────────────────────────────────── */
export function EmptyState({ icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      {icon && <div className="w-12 h-12 mb-4 text-surface-300 dark:text-surface-600">{icon}</div>}
      <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 mb-1">{title}</h3>
      {description && <p className="text-xs text-surface-400 dark:text-surface-500 max-w-xs mb-4">{description}</p>}
      {action}
    </div>
  )
}

/* ─── Skeleton ───────────────────────────────────────────── */
export function Skeleton({ className }) {
  return <div className={cn('skeleton rounded-lg', className)} />
}
