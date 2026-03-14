import { Activity } from 'lucide-react'
import type { SecurityEvent } from '../types'

interface ActivityEntry {
  time: string
  provider: string
  msgs: number
  latency: number
  status: number
  snippet: string
}

function toEntry(ev: SecurityEvent): ActivityEntry {
  const d = ev.data
  return {
    time: ev.timestamp?.split('T')[1]?.replace('Z', '') ?? '',
    provider: (d.provider as string) ?? '?',
    msgs: (d.message_count as number) ?? 0,
    latency: (d.latency_ms as number) ?? 0,
    status: (d.status as number) ?? 200,
    snippet: (d.last_user_message as string) ?? '',
  }
}

interface Props {
  events: SecurityEvent[]
}

export function ActivityLog({ events }: Props) {
  const responses = events
    .filter((e) => e.type === 'LLM_RESPONSE')
    .slice(0, 50)
    .map(toEntry)

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 mb-3 px-1">
        <Activity className="w-3.5 h-3.5 text-muted" />
        <h2 className="text-[13px] font-semibold text-muted uppercase tracking-wider">
          Proxy Activity
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {responses.length === 0 ? (
          <div className="text-center py-10 text-muted text-xs opacity-50">
            No proxy traffic yet
          </div>
        ) : (
          responses.map((e, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface2/60 border border-border/50 text-[12px] hover:bg-surface2 transition-colors"
            >
              <span className="font-mono text-muted w-16 flex-shrink-0">{e.time}</span>
              <span className="font-semibold text-blue w-20 flex-shrink-0">{e.provider}</span>
              <span className="text-muted flex-shrink-0">{e.msgs}m</span>
              <span className="text-text/70 flex-1 truncate font-mono text-[11px]">
                {e.snippet.slice(0, 50)}
              </span>
              <span
                className={`font-mono font-semibold flex-shrink-0 ${
                  e.status >= 400 ? 'text-red' : e.latency > 3000 ? 'text-yellow' : 'text-green'
                }`}
              >
                {e.latency}ms
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
