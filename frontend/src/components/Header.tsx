import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Lock, Unlock, Cpu } from 'lucide-react'
import type { Stats } from '../types'

interface Props {
  connected: boolean
  stats: Stats | null
  blockMode: boolean
  onToggleBlock: () => void
}

function StatPill({
  label,
  value,
  accent,
}: {
  label: string
  value: number
  accent?: string
}) {
  return (
    <div className="flex flex-col items-center px-4 py-1.5">
      <AnimatePresence mode="wait">
        <motion.span
          key={value}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.15 }}
          className={`text-xl font-bold tabular-nums ${accent ?? 'text-text'}`}
        >
          {value}
        </motion.span>
      </AnimatePresence>
      <span className="text-[10px] text-muted uppercase tracking-widest mt-0.5">{label}</span>
    </div>
  )
}

export function Header({ connected, stats, blockMode, onToggleBlock }: Props) {
  const counts = stats?.counts ?? { total: 0, injection: 0, blocked: 0, tool_calls: 0 }
  const hardening = stats?.hardening
  const kernelActive = hardening?.landlock_active || hardening?.seatbelt_active

  return (
    <header className="flex-shrink-0 border-b border-border bg-surface/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex items-center justify-between px-5 py-3 gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <Shield className="w-7 h-7 text-blue" strokeWidth={1.5} />
            <span
              className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full border-2 border-surface ${
                connected ? 'bg-green' : 'bg-red'
              }`}
            />
          </div>
          <div>
            <span className="font-bold text-[15px] text-text tracking-tight">ClawShield</span>
            <div className="flex items-center gap-1.5 mt-0">
              <span
                className={`text-[10px] font-medium ${connected ? 'text-green' : 'text-red'}`}
              >
                {connected ? 'Connected' : 'Reconnecting…'}
              </span>
              {kernelActive !== undefined && (
                <>
                  <span className="text-muted text-[10px]">·</span>
                  <span
                    className={`text-[10px] font-medium ${kernelActive ? 'text-green' : 'text-yellow'}`}
                  >
                    {kernelActive
                      ? hardening?.landlock_active
                        ? 'Landlock'
                        : 'Seatbelt'
                      : 'Kernel hardening inactive'}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-stretch divide-x divide-border rounded-lg border border-border bg-bg overflow-hidden">
          <StatPill label="Events" value={counts.total} />
          <StatPill label="Threats" value={counts.injection} accent={counts.injection > 0 ? 'text-yellow' : undefined} />
          <StatPill label="Blocked" value={counts.blocked} accent={counts.blocked > 0 ? 'text-red' : undefined} />
          <StatPill label="Tools" value={counts.tool_calls} />
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {hardening && (
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium border ${
                kernelActive
                  ? 'border-green/30 text-green bg-green/5'
                  : 'border-yellow/30 text-yellow bg-yellow/5'
              }`}
              title={`Platform: ${hardening.platform}`}
            >
              <Cpu className="w-3 h-3" />
              {kernelActive ? 'Hardened' : 'Unhardened'}
            </div>
          )}

          <button
            onClick={onToggleBlock}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-[13px] font-semibold border transition-all duration-200 ${
              blockMode
                ? 'bg-red/10 border-red/40 text-red hover:bg-red/15'
                : 'bg-surface2 border-border text-muted hover:text-text hover:border-text/30'
            }`}
          >
            {blockMode ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
            {blockMode ? 'Blocking ON' : 'Blocking OFF'}
          </button>

          <a
            href="/wizard-page"
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-[13px] font-semibold border border-blue/30 text-blue bg-blue/5 hover:bg-blue/10 transition-colors"
          >
            Setup Wizard
          </a>
        </div>
      </div>
    </header>
  )
}
