import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  text: string
  ts: string
}

const AGENT_URL = '/agent-chat'  // proxied by Aegis to agent:8001

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [agentName, setAgentName] = useState('Agent')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch(`${AGENT_URL}/health`)
      .then((r) => r.json())
      .then((d) => setAgentName(d.agent ?? 'Agent'))
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')

    const userMsg: Message = { role: 'user', text, ts: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch(`${AGENT_URL}/chat`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: data.response ?? '(no response)', ts: new Date().toISOString() },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: '(connection error — is the agent running?)', ts: new Date().toISOString() },
      ])
    } finally {
      setLoading(false)
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 mb-3 px-1">
        <Bot className="w-3.5 h-3.5 text-muted" />
        <h2 className="text-[13px] font-semibold text-muted uppercase tracking-wider">
          {agentName}
        </h2>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 mb-3">
        {messages.length === 0 && (
          <div className="text-center py-10 text-muted text-xs opacity-50">
            Send a message to start chatting with your agent
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
              className={`flex gap-2.5 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div
                className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
                  m.role === 'user' ? 'bg-blue/20' : 'bg-surface2'
                }`}
              >
                {m.role === 'user' ? (
                  <User className="w-3.5 h-3.5 text-blue" />
                ) : (
                  <Bot className="w-3.5 h-3.5 text-muted" />
                )}
              </div>
              <div
                className={`max-w-[80%] px-3.5 py-2.5 rounded-2xl text-[13px] leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-blue/15 text-text rounded-tr-sm'
                    : 'bg-surface2 text-text/90 rounded-tl-sm'
                }`}
              >
                {m.text}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <div className="flex gap-2.5">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-surface2 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-muted" />
            </div>
            <div className="px-3.5 py-2.5 rounded-2xl rounded-tl-sm bg-surface2 flex gap-1 items-center">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-muted"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 items-end">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Message your agent…"
          rows={1}
          className="flex-1 bg-surface2 border border-border rounded-xl px-3.5 py-2.5 text-[13px] text-text placeholder:text-muted outline-none focus:border-blue/50 transition-colors resize-none font-sans leading-relaxed"
          style={{ maxHeight: '100px', overflowY: 'auto' }}
        />
        <button
          onClick={send}
          disabled={!input.trim() || loading}
          className="flex-shrink-0 w-9 h-9 rounded-xl bg-blue/10 border border-blue/30 text-blue flex items-center justify-center hover:bg-blue/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
