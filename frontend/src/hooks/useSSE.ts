import { useEffect, useRef, useState } from 'react'
import type { SecurityEvent } from '../types'

const MAX_EVENTS = 200

export function useSSE() {
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [connected, setConnected] = useState(false)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    function connect() {
      if (sourceRef.current) sourceRef.current.close()

      const es = new EventSource('/events')
      sourceRef.current = es

      es.onopen = () => setConnected(true)

      es.onmessage = (e) => {
        try {
          const ev: SecurityEvent = JSON.parse(e.data)
          if (ev.type === 'PING') return
          setEvents((prev) => {
            const next = [ev, ...prev]
            return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next
          })
        } catch {
          // ignore parse errors
        }
      }

      es.onerror = () => {
        setConnected(false)
        es.close()
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => sourceRef.current?.close()
  }, [])

  return { events, connected }
}
