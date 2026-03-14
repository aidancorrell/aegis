import { AnimatePresence } from 'framer-motion'
import { ShieldAlert } from 'lucide-react'
import type { SecurityEvent } from '../types'
import { EventCard } from './EventCard'

interface Props {
  events: SecurityEvent[]
}

export function EventFeed({ events }: Props) {
  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-1 mb-3">
        <h2 className="text-[13px] font-semibold text-muted uppercase tracking-wider">
          Live Events
        </h2>
        <span className="text-[11px] text-muted">{events.length} captured</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-20 opacity-40">
            <ShieldAlert className="w-10 h-10 text-muted mb-3" strokeWidth={1.5} />
            <p className="text-sm text-muted">Waiting for events…</p>
            <p className="text-xs text-muted mt-1">Send a message to your agent to get started</p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {events.map((ev, i) => (
              <EventCard key={`${ev.timestamp}-${i}`} event={ev} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
