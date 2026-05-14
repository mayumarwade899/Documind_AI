import { api, getSessionId } from './api.js'

export async function ingestFile(file, forceReingest = false, onProgress) {
  const sessionId = getSessionId()
  const form = new FormData()
  form.append('file', file)
  return api.postForm(`/ingest/file?session_id=${sessionId}&force_reingest=${forceReingest}`, form, onProgress)
}

export async function ingestDirectory(dirPath = 'data/documents', forceReingest = false) {
  const sessionId = getSessionId()
  return api.post('/ingest/directory', { session_id: sessionId, dir_path: dirPath, force_reingest: forceReingest })
}

export async function getIngestStatus() {
  const sessionId = getSessionId()
  return api.get(`/ingest/status/${sessionId}`)
}

export async function getDocuments() {
  const sessionId = getSessionId()
  return api.get(`/ingest/documents/${sessionId}`)
}

export async function deleteDocument(documentId) {
  const sessionId = getSessionId()
  return api.del(`/ingest/documents/${sessionId}/${encodeURIComponent(documentId)}`)
}
