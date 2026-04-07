import { useState, useRef, useCallback } from 'react'
import { BASE } from '../services/api.js'

export function useSSEStream() {
  const [streamedText, setStreamedText] = useState('')
  const [isStreaming, setIsStreaming]   = useState(false)
  const [streamMeta, setStreamMeta]     = useState(null)
  const [error, setError]               = useState(null)
  const readerRef = useRef(null)
  const abortRef  = useRef(null)

  const stream = useCallback(async (payload, { onToken, onComplete, onError } = {}) => {
    abortRef.current = new AbortController()
    setStreamedText('')
    setStreamMeta(null)
    setError(null)
    setIsStreaming(true)

    try {
      const res = await fetch(`${BASE}/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}))
        throw new Error(errBody.detail ?? `HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      readerRef.current = reader
      const decoder = new TextDecoder()
      let buffer = ''
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') break

          try {
            const data = JSON.parse(raw)
            if (data.type === 'token' && data.content) {
              fullText += data.content
              setStreamedText(fullText)
              onToken?.(data.content, fullText)
            } else if (data.type === 'metadata') {
              setStreamMeta(data)
            } else if (data.type === 'error') {
              throw new Error(data.message)
            }
          } catch (parseErr) {
            // non-JSON SSE line, skip
          }
        }
      }

      setIsStreaming(false)
      onComplete?.(fullText, streamMeta)
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message)
      setIsStreaming(false)
      onError?.(err)
    }
  }, [])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    readerRef.current?.cancel()
    setIsStreaming(false)
  }, [])

  const reset = useCallback(() => {
    setStreamedText('')
    setStreamMeta(null)
    setError(null)
    setIsStreaming(false)
  }, [])

  return { streamedText, isStreaming, streamMeta, error, stream, stop, reset }
}
