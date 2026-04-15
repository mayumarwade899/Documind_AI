import { api } from './api.js'


export async function runEvaluation(maxQuestions = null) {
  const params = maxQuestions ? `?max_questions=${maxQuestions}` : ''
  return api.post(`/evaluation/run${params}`)
}

export async function getEvaluationStatus() {
  return api.get('/evaluation/status')
}
