import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldAlert, ShieldX, KeyRound, X } from 'lucide-react'
import type { SecurityEvent } from '../types'

interface Toast {
  id: string
  event: SecurityEvent
}

const TOAST_TTL_MS = 6000

const TOAST_CONFIG: Record<string, { icon: typeof ShieldX; label: string; styles: string }> = {
  INJECTION_BLOCKED: {
    icon: ShieldX,
    label: 'Injection Blocked',
    styles: 'border-red/60 bg-red/10 text-red shadow-[0_0_30px_rgba(248,81,73,0.3)]',
  },
  INJECTION_PROBE: {
    icon: ShieldAlert,
    label: 'Injection Detected',
    styles: 'border-yellow/60 bg-yellow/10 text-yellow shadow-[0_0_30px_rgba(210,153,34,0.3)]',
  },
  CREDENTIAL_LEAK: {
    icon: KeyRound,
    label: 'Credential Leak',
    styles: 'border-orange/60 bg-orange/10 text-orange shadow-[0_0_30px_rgba(227,179,65,0.3)]',
  },
  TOOL_BLOCKED: {
    icon: ShieldAlert,
    label: 'Tool Blocked',
    styles: 'border-orange/60 bg-orange/10 text-orange shadow-[0_0_30px_rgba(227,179,65,0.3)]',
  },
}

export function useThreatToasts(events: SecurityEvent[]) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [seen, setSeen] = useState(new Set<string>())

  useEffect(() => {
    const latest = events[0]
    if (!latest) return
    if (!TOAST_CONFIG[latest.type]) return

    const id = `${latest.type}-${latest.timestamp}`
    if (seen.has(id)) return

    setSeen((prev) => new Set([...prev, id]))
    const toast: Toast = { id, event: latest }
    setToasts((prev) => [toast, ...prev].slice(0, 3))

    const timer = setTimeout(
      () => setToasts((prev) => prev.filter((t) => t.id !== id)),
      TOAST_TTL_MS
    )
    return () => clearTimeout(timer)
  }, [events])

  function dismiss(id: string) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  return { toasts, dismiss }
}

export function ThreatToasts({
  toasts,
  onDismiss,
}: {
  toasts: Toast[]
  onDismiss: (id: string) => void
}) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map(({ id, event }) => {
          const cfg = TOAST_CONFIG[event.type]
          if (!cfg) return null
          const Icon = cfg.icon
          const d = event.data

          const detail =
            event.type === 'INJECTION_BLOCKED'
              ? 'Payload replaced — LLM never saw the attack'
              : event.type === 'INJECTION_PROBE'
              ? ((d.patterns as string[]) ?? []).slice(0, 2).join(', ')
              : event.type === 'CREDENTIAL_LEAK'
              ? (d.note as string) ?? ''
              : (d.error as string) ?? ''

          return (
            <motion.div
              key={id}
              initial={{ opacity: 0, x: 60, scale: 0.92 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 60, scale: 0.92 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className={`pointer-events-auto w-80 rounded-xl border-2 px-4 py-3 backdrop-blur-sm ${cfg.styles}`}
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                  <Icon className="w-5 h-5" strokeWidth={2} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-[14px]">{cfg.label}</div>
                  {detail && (
                    <div className="text-[12px] opacity-80 mt-0.5 font-mono truncate">{detail}</div>
                  )}
                  {event.type === 'INJECTION_BLOCKED' && (
                    <div className="text-[11px] opacity-70 mt-1">
                      Payload replaced before reaching the LLM
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onDismiss(id)}
                  className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Auto-dismiss progress bar */}
              <motion.div
                className="mt-2.5 h-0.5 rounded-full bg-current opacity-30"
                initial={{ scaleX: 1 }}
                animate={{ scaleX: 0 }}
                transition={{ duration: TOAST_TTL_MS / 1000, ease: 'linear' }}
                style={{ transformOrigin: 'left' }}
              />
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
