import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle } from 'lucide-react'

export function ConfirmDialog({ 
  isOpen, 
  title, 
  message, 
  confirmText = 'Confirm', 
  cancelText = 'Cancel',
  isDangerous = false,
  onConfirm, 
  onCancel 
}) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCancel}
            className="fixed inset-0 bg-black/50 z-40"
          />
          
          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: 'spring', damping: 20, stiffness: 300 }}
            className="fixed inset-0 flex items-center justify-center z-50 pointer-events-none"
          >
            <div className="bg-white dark:bg-surface-800 rounded-lg shadow-lg max-w-sm w-[90%] pointer-events-auto border border-surface-200 dark:border-surface-700">
              {/* Header */}
              <div className={`flex items-start gap-3 px-6 py-4 border-b border-surface-200 dark:border-surface-700 ${isDangerous ? 'bg-red-50 dark:bg-red-950/20' : ''}`}>
                <div className={`flex-shrink-0 mt-0.5 ${isDangerous ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}`}>
                  <AlertCircle size={20} />
                </div>
                <div className="flex-1">
                  <h2 className={`font-semibold text-surface-900 dark:text-surface-50 ${isDangerous ? 'text-red-900 dark:text-red-200' : ''}`}>
                    {title}
                  </h2>
                </div>
              </div>

              {/* Body */}
              <div className="px-6 py-4">
                <p className="text-surface-700 dark:text-surface-300 text-sm leading-relaxed">
                  {message}
                </p>
              </div>

              {/* Footer */}
              <div className="flex justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-900/50">
                <button
                  onClick={onCancel}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-surface-700 dark:text-surface-300 bg-white dark:bg-surface-700 border border-surface-300 dark:border-surface-600 hover:bg-surface-100 dark:hover:bg-surface-600 transition-colors"
                >
                  {cancelText}
                </button>
                <button
                  onClick={onConfirm}
                  className={`px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors ${
                    isDangerous
                      ? 'bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600'
                      : 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600'
                  }`}
                >
                  {confirmText}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
