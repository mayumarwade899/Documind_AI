import { api } from './api.js'

export async function getMetrics(days = 7) {
  return api.get(`/metrics?days=${days}`)
}

export async function getLatency(days = 7) {
  return api.get(`/metrics/latency?days=${days}`)
}

export async function getDailyMetrics(days = 7) {
  return api.get(`/metrics/daily?days=${days}`)
}

export async function getHealthStatus() {
  return api.get('/health')
}
