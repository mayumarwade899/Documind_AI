import { cn } from '../../utils/cn.js'

/**
 * Reusable page header bar.
 *
 * <TopBar
 *   title="Documents"
 *   subtitle="Manage your knowledge base"
 *   actions={<Button>Upload</Button>}
 * />
 */
export function TopBar({ title, subtitle, actions, className, children }) {
  return (
    <div className={cn(
      'flex items-center justify-between h-14 px-6 border-b border-surface-200 dark:border-surface-700',
      'bg-white dark:bg-surface-900 shrink-0',
      className
    )}>
      <div className="min-w-0">
        <h1 className="text-base font-semibold text-surface-900 dark:text-white leading-tight">{title}</h1>
        {subtitle && (
          <p className="text-xs text-surface-400 mt-0.5 truncate">{subtitle}</p>
        )}
      </div>
      {(actions || children) && (
        <div className="flex items-center gap-2 shrink-0 ml-4">
          {actions}
          {children}
        </div>
      )}
    </div>
  )
}
