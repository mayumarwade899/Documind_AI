import { api } from './api.js'

export async function getGoldenDataset() {
  return api.get('/evaluation/dataset')
}

export async function getDatasetStats() {
  return api.get('/evaluation/stats')
}

export async function getLatestReport() {
  return api.get('/evaluation/latest')
}

export async function runEvaluation(maxQuestions = null) {
  const params = maxQuestions ? `?max_questions=${maxQuestions}` : ''
  return api.post(`/evaluation/run${params}`)
}
