import { api, getSessionId } from './api.js'

export async function runEvaluation(maxQuestions = null) {
  const sessionId = getSessionId()
  const params = maxQuestions ? `?max_questions=${maxQuestions}` : ''
  return api.post(`/evaluation/run/${sessionId}${params}`)
}

export async function getEvaluationStatus() {
  const sessionId = getSessionId()
  return api.get(`/evaluation/status/${sessionId}`)
}

export async function getEvaluationLatest() {
  const sessionId = getSessionId()
  return api.get(`/evaluation/latest/${sessionId}`)
}

export async function getEvaluationHistory() {
  const sessionId = getSessionId()
  return api.get(`/evaluation/history/${sessionId}`)
}
