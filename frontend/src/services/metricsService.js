import { api, getSessionId } from './api.js'

export async function getMetrics(days = 7) {
  const sessionId = getSessionId()
  return api.get(`/metrics/${sessionId}?days=${days}`)
}

export async function getMetricsLatency(days = 7) {
  const sessionId = getSessionId()
  return api.get(`/metrics/${sessionId}/latency?days=${days}`)
}

export async function getDailyMetrics(days = 7) {
  const sessionId = getSessionId()
  return api.get(`/metrics/${sessionId}/daily?days=${days}`)
}

export async function getHealthStatus() {
  return api.get('/health')
}
