import { useState } from 'react'
import { ChevronDown, ChevronUp, Wand2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../../utils/cn.js'

export function QueryRewriteDisplay({ original, rewritten, variants = [], numQueries = 1 }) {
  const [open, setOpen] = useState(false)

  if (!rewritten || rewritten === original) return null

  return (
    <div className="mb-3 text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors"
      >
        <Wand2 size={11} />
        <span className="font-medium">Query rewritten</span>
        {numQueries > 1 && (
          <span className="ml-1 px-1.5 py-0.5 rounded-full bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300 text-[10px] font-semibold">
            {numQueries} variants
          </span>
        )}
        {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="mt-2 p-3 rounded-lg bg-surface-50 dark:bg-surface-800/60 border border-surface-200 dark:border-surface-700 space-y-2">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-1">Original</p>
                <p className="text-surface-500 dark:text-surface-400 line-through opacity-70">{original}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-1">Rewritten</p>
                <p className="text-brand-700 dark:text-brand-300 font-medium">{rewritten}</p>
              </div>
              {variants.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-surface-400 mb-1">Variants</p>
                  <ol className="space-y-1">
                    {variants.map((v, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-surface-300 dark:text-surface-600 shrink-0">{i + 1}.</span>
                        <span className="text-surface-600 dark:text-surface-400">{v}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
