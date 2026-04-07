import { api, BASE } from './api.js'

export async function queryRAG(payload) {
  return api.post('/query', payload)
}

export async function submitFeedback(payload) {
  return api.post('/feedback', payload)
}

export async function getFeedbackSummary(days = 30) {
  return api.get(`/feedback/summary?days=${days}`)
}

export async function getNegativeFeedback(days = 30) {
  return api.get(`/feedback/negative?days=${days}`)
}

// SSE streaming query — returns a ReadableStream reader
export async function streamQuery(payload) {
  const res = await fetch(`${BASE}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.body.getReader()
}
