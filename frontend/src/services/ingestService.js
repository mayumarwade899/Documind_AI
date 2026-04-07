import { api } from './api.js'

export async function ingestFile(file, forceReingest = false, onProgress) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm(`/ingest/file?force_reingest=${forceReingest}`, form, onProgress)
}

export async function ingestDirectory(dirPath = 'data/documents', forceReingest = false) {
  return api.post('/ingest/directory', { dir_path: dirPath, force_reingest: forceReingest })
}

export async function getIngestStatus() {
  return api.get('/ingest/status')
}

export async function getDocuments() {
  return api.get('/ingest/documents')
}
