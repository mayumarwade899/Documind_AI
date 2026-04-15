import { formatDistanceToNow, format } from 'date-fns'

export function formatCost(usd) {
  if (usd === 0) return '$0.00'
  if (usd < 0.0001) return `$${usd.toExponential(2)}`
  if (usd < 0.01)   return `$${usd.toFixed(5)}`
  return `$${usd.toFixed(4)}`
}

export function formatTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return n.toLocaleString()
}

export function formatLatency(ms) {
  if (!ms) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms)}ms`
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function timeAgo(dateStr) {
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true })
  } catch { return dateStr }
}


export function formatPercent(ratio, decimals = 1) {
  if (ratio == null) return '—'
  return `${(ratio * 100).toFixed(decimals)}%`
}
