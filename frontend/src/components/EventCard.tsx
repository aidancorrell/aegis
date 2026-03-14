import { motion } from 'framer-motion'
import type { SecurityEvent } from '../types'

const TYPE_LABELS: Record<string, string> = {
  LLM_REQUEST: 'LLM Request',
  LLM_RESPONSE: 'LLM Response',
  TOOL_CALL: 'Tool Call',
  TOOL_BLOCKED: 'Tool Blocked',
  INJECTION_PROBE: 'Injection Detected',
  INJECTION_BLOCKED: 'Injection Blocked',
  CREDENTIAL_LEAK: 'Credential Leak',
  RATE_LIMIT_HIT: 'Rate Limited',
}

const SEVERITY_STYLES = {
  info: {
    card: 'border-blue-500/20 bg-blue-500/[0.03]',
    badge: 'bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30',
    dot: 'bg-blue-400',
    glow: '',
  },
  warn: {
    card: 'border-yellow-500/30 bg-yellow-500/[0.04]',
    badge: 'bg-yellow-500/15 text-yellow-400 ring-1 ring-yellow-500/30',
    dot: 'bg-yellow-400',
    glow: '',
  },
  high: {
    card: 'border-orange-500/40 bg-orange-500/[0.06]',
    badge: 'bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/30',
    dot: 'bg-orange-400',
    glow: 'shadow-[0_0_12px_rgba(249,115,22,0.15)]',
  },
  critical: {
    card: 'border-red-500/50 bg-red-500/[0.08]',
    badge: 'bg-red-500/20 text-red-400 ring-1 ring-red-500/40',
    dot: 'bg-red-500',
    glow: 'shadow-[0_0_20px_rgba(248,81,73,0.25)]',
  },
}

function getBody(ev: SecurityEvent): { main: string; snippet?: string } {
  const d = ev.data
  switch (ev.type) {
    case 'LLM_REQUEST':
      return {
        main: `${d.provider ?? '?'} · ${d.message_count ?? 0} msgs · ${d.tool_count ?? 0} tools`,
        snippet: d.last_user_message as string | undefined,
      }
    case 'LLM_RESPONSE':
      return {
        main: `${d.provider ?? '?'} · ${d.latency_ms ?? 0}ms · HTTP ${d.status ?? 200}`,
      }
    case 'TOOL_CALL': {
      const args = (d.args as Record<string, unknown>) ?? {}
      const argStr = Object.entries(args)
        .map(([k, v]) => `${k}=${String(v).slice(0, 40)}`)
        .join(' · ')
      return { main: `${d.tool ?? '?'}${argStr ? '  ' + argStr : ''}` }
    }
    case 'TOOL_BLOCKED':
      return { main: `${d.tool ?? '?'} · ${String(d.error ?? '').slice(0, 100)}` }
    case 'INJECTION_PROBE':
    case 'INJECTION_BLOCKED': {
      const patterns = ((d.patterns as string[]) ?? []).slice(0, 3).join(', ')
      return { main: patterns, snippet: d.snippet as string | undefined }
    }
    case 'CREDENTIAL_LEAK':
      return { main: `${d.provider ?? '?'} · ${d.note ?? ''}` }
    default:
      return { main: JSON.stringify(d).slice(0, 120) }
  }
}

export function EventCard({ event }: { event: SecurityEvent }) {
  const sev = SEVERITY_STYLES[event.severity] ?? SEVERITY_STYLES.info
  const label = TYPE_LABELS[event.type] ?? event.type
  const time = event.timestamp?.split('T')[1]?.replace('Z', '') ?? ''
  const { main, snippet } = getBody(event)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`rounded-lg border px-4 py-3 ${sev.card} ${sev.glow} transition-shadow`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2">
          <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${sev.dot}`} />
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${sev.badge}`}>
            {label}
          </span>
        </div>
        <span className="text-[11px] text-muted font-mono flex-shrink-0">{time}</span>
      </div>
      <p className="text-[13px] text-text/80 font-mono leading-snug truncate">{main}</p>
      {snippet && (
        <p className="mt-1.5 text-[11px] text-muted leading-relaxed line-clamp-2 font-mono border-t border-border/50 pt-1.5">
          {snippet.slice(0, 200)}
        </p>
      )}
    </motion.div>
  )
}
