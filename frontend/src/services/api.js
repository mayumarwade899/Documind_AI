const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

class APIError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.detail = detail
  }
}

async function request(path, options = {}) {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {}
    throw new APIError(detail, res.status, detail)
  }

  if (res.status === 204) return null
  return res.json()
}

async function postForm(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}${path}`)

    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
      })
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        let detail = `HTTP ${xhr.status}`
        try { detail = JSON.parse(xhr.responseText).detail ?? detail } catch {}
        reject(new APIError(detail, xhr.status, detail))
      }
    }
    xhr.onerror = () => reject(new APIError('Network error', 0, 'Network error'))
    xhr.send(formData)
  })
}

export const api = {
  get:      (path, opts)       => request(path, { method: 'GET', ...opts }),
  post:     (path, body, opts) => request(path, { method: 'POST', body: JSON.stringify(body), ...opts }),
  del:      (path, opts)       => request(path, { method: 'DELETE', ...opts }),
  postForm: (path, fd, onProg) => postForm(path, fd, onProg),
}

export { APIError, BASE }
