import { api, BASE, getSessionId } from './api.js'

export async function queryRAG(payload) {
  const sessionId = getSessionId()
  return api.post('/query', { ...payload, session_id: sessionId })
}

export async function submitFeedback(payload) {
  const sessionId = getSessionId()
  return api.post('/feedback', { ...payload, session_id: sessionId })
}

export async function getFeedbackSummary(days = 30) {
  return api.get(`/feedback/summary?days=${days}`)
}

export async function getNegativeFeedback(days = 30) {
  return api.get(`/feedback/negative?days=${days}`)
}

export async function getChatHistory(sessionId) {
  return api.get(`/query/history/${sessionId}`)
}

export async function clearChatHistory(sessionId) {
  return api.del(`/query/history/${sessionId}`)
}

export async function streamQuery(payload) {
  const sessionId = getSessionId()
  const body = { ...payload, session_id: sessionId }
  const res = await fetch(`${BASE}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.body.getReader()
}
