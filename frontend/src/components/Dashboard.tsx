import { useState, useEffect } from 'react'
import { Header } from './Header'
import { EventFeed } from './EventFeed'
import { ActivityLog } from './ActivityLog'
import { Chat } from './Chat'
import { useSSE } from '../hooks/useSSE'
import type { Stats } from '../types'

type RightTab = 'activity' | 'chat'

export function Dashboard() {
  const { events, connected } = useSSE()
  const [stats, setStats] = useState<Stats | null>(null)
  const [blockMode, setBlockMode] = useState(true)
  const [rightTab, setRightTab] = useState<RightTab>('activity')
  const [agentOnline, setAgentOnline] = useState(false)

  useEffect(() => {
    fetch('/stats')
      .then((r) => r.json())
      .then((data: Stats) => {
        setStats(data)
        setBlockMode(data.block_injections)
      })
      .catch(() => {})

    // Check if agent-builder chat is available
    fetch('/agent-chat/health')
      .then((r) => r.ok && setAgentOnline(true))
      .catch(() => {})
  }, [])

  async function toggleBlock() {
    const next = !blockMode
    setBlockMode(next)
    await fetch(`/settings/block-injections?enabled=${next}`, { method: 'POST' }).catch(() => {})
  }

  return (
    <div className="flex flex-col h-screen bg-bg text-text font-sans overflow-hidden">
      <Header
        connected={connected}
        stats={stats}
        blockMode={blockMode}
        onToggleBlock={toggleBlock}
      />

      <div className="flex flex-1 min-h-0 gap-0">
        {/* Left panel — event feed */}
        <div className="flex-1 min-w-0 p-4 overflow-hidden flex flex-col border-r border-border">
          <EventFeed events={events} />
        </div>

        {/* Right panel — tabs */}
        <div className="w-[420px] flex-shrink-0 flex flex-col overflow-hidden">
          {/* Tab bar */}
          <div className="flex border-b border-border px-4 pt-3 gap-1 flex-shrink-0">
            <button
              onClick={() => setRightTab('activity')}
              className={`px-3 py-1.5 text-[12px] font-medium rounded-t-md transition-colors ${
                rightTab === 'activity'
                  ? 'text-text border-b-2 border-blue -mb-px'
                  : 'text-muted hover:text-text'
              }`}
            >
              Proxy Activity
            </button>
            <button
              onClick={() => setRightTab('chat')}
              className={`px-3 py-1.5 text-[12px] font-medium rounded-t-md transition-colors flex items-center gap-1.5 ${
                rightTab === 'chat'
                  ? 'text-text border-b-2 border-blue -mb-px'
                  : 'text-muted hover:text-text'
              }`}
            >
              Chat
              {agentOnline && (
                <span className="w-1.5 h-1.5 rounded-full bg-green" />
              )}
            </button>
          </div>

          <div className="flex-1 min-h-0 p-4 overflow-hidden flex flex-col">
            {rightTab === 'activity' ? (
              <ActivityLog events={events} />
            ) : (
              <Chat />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
