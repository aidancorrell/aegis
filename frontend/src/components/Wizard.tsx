import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Zap, ChevronRight, ChevronLeft, Copy, Check, ExternalLink } from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

type Mode = 'connect' | 'build'

interface AgentProfile {
  name: string
  description: string
  compatibility: string
  image: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function useCopy(text: string) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return { copy, copied }
}

// ─── Shared UI ───────────────────────────────────────────────────────────────

function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {Array.from({ length: total }, (_, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <div key={n} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold transition-all ${
                done
                  ? 'bg-green text-bg'
                  : active
                  ? 'bg-blue/20 border-2 border-blue text-blue'
                  : 'border-2 border-border text-muted'
              }`}
            >
              {done ? <Check className="w-4 h-4" /> : n}
            </div>
            {i < total - 1 && (
              <div className={`w-12 h-0.5 ${n < current ? 'bg-green' : 'bg-border'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-6 mb-4">{children}</div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-[13px] font-semibold text-text mb-1.5">{children}</label>
}

function Hint({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] text-muted mt-1">{children}</p>
}

function Input({
  id,
  type = 'text',
  placeholder,
  value,
  onChange,
}: {
  id?: string
  type?: string
  placeholder?: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <input
      id={id}
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-[14px] text-text placeholder:text-muted outline-none focus:border-blue transition-colors font-sans"
    />
  )
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-[14px] text-text outline-none focus:border-blue transition-colors"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

function CodeBlock({ id, content }: { id: string; content: string }) {
  const { copy, copied } = useCopy(content)
  return (
    <div className="relative">
      <pre
        id={id}
        className="bg-bg border border-border rounded-lg p-3 text-[12px] font-mono text-green overflow-auto max-h-48 whitespace-pre-wrap break-all"
      >
        {content}
      </pre>
      <button
        onClick={copy}
        className="absolute top-2 right-2 p-1.5 rounded bg-surface2 border border-border text-muted hover:text-text transition-colors"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-green" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </div>
  )
}

function Nav({
  onBack,
  onNext,
  nextLabel = 'Next',
  nextDisabled,
  loading,
}: {
  onBack?: () => void
  onNext: () => void
  nextLabel?: string
  nextDisabled?: boolean
  loading?: boolean
}) {
  return (
    <div className="flex justify-between items-center mt-6">
      {onBack ? (
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-border text-muted hover:text-text hover:border-text/30 text-[13px] font-medium transition-colors"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
      ) : (
        <div />
      )}
      <button
        onClick={onNext}
        disabled={nextDisabled || loading}
        className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-blue text-bg text-[13px] font-semibold hover:bg-blue/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        {loading ? 'Generating…' : nextLabel}
        {!loading && <ChevronRight className="w-4 h-4" />}
      </button>
    </div>
  )
}

const slideVariants = {
  enter: { x: 30, opacity: 0 },
  center: { x: 0, opacity: 1 },
  exit: { x: -30, opacity: 0 },
}

// ─── Mode A: Connect Agent ────────────────────────────────────────────────────

function ConnectAgentWizard({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState(1)
  const [agents, setAgents] = useState<AgentProfile[]>([])
  const [selected, setSelected] = useState('mako')
  const [provider, setProvider] = useState('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [telegramToken, setTelegramToken] = useState('')
  const [discordToken, setDiscordToken] = useState('')
  const [result, setResult] = useState<Record<string, string> | null>(null)
  const [loading, setLoading] = useState(false)
  const TOTAL = 4

  useEffect(() => {
    fetch('/wizard/agents')
      .then((r) => r.json())
      .then((d) => setAgents(d.agents))
      .catch(() => {})
  }, [])

  async function generate() {
    setLoading(true)
    try {
      const res = await fetch('/wizard/generate', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          agent_name: selected,
          llm_provider: provider,
          llm_api_key: apiKey || 'CHANGEME',
          telegram_bot_token: telegramToken,
          discord_bot_token: discordToken,
        }),
      })
      setResult(await res.json())
    } catch {
      setResult({ error: 'Failed to generate config' })
    } finally {
      setLoading(false)
    }
  }

  function next() {
    if (step < TOTAL) setStep(step + 1)
    if (step === TOTAL - 1) generate()
  }

  return (
    <div>
      <StepIndicator current={step} total={TOTAL} />
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          variants={slideVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          {step === 1 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">Choose Agent</h2>
              <p className="text-[13px] text-muted mb-5">
                Select the OpenClaw-compatible agent ClawShield will wrap
              </p>
              <div className="space-y-2">
                {agents.map((a) => (
                  <button
                    key={a.name}
                    onClick={() => setSelected(a.name)}
                    className={`w-full flex items-center gap-3 p-4 rounded-lg border text-left transition-all ${
                      selected === a.name
                        ? 'border-blue bg-blue/5'
                        : 'border-border bg-surface2/50 hover:border-border/80'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-[14px] capitalize">{a.name}</div>
                      <div className="text-[12px] text-muted truncate">{a.image}</div>
                      <div className="text-[12px] text-muted">{a.description}</div>
                    </div>
                    <span className="text-[11px] text-green flex-shrink-0">{a.compatibility}</span>
                  </button>
                ))}
              </div>
            </Card>
          )}

          {step === 2 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">API Keys</h2>
              <p className="text-[13px] text-muted mb-5">
                Stored in <span className="font-mono text-blue">clawshield.env</span> only — never
                inside the agent container.
              </p>
              <div className="space-y-4">
                <div>
                  <Label>LLM Provider</Label>
                  <Select
                    value={provider}
                    onChange={setProvider}
                    options={[
                      { value: 'anthropic', label: 'Anthropic Claude' },
                      { value: 'gemini', label: 'Google Gemini' },
                      { value: 'openai', label: 'OpenAI' },
                    ]}
                  />
                </div>
                <div>
                  <Label>API Key</Label>
                  <Input
                    type="password"
                    placeholder="Paste your API key"
                    value={apiKey}
                    onChange={setApiKey}
                  />
                  <Hint>Stored on the host only. The agent receives a dummy key.</Hint>
                </div>
              </div>
            </Card>
          )}

          {step === 3 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">Bot Channels</h2>
              <p className="text-[13px] text-muted mb-5">
                Dashboard always at localhost:8000. Optionally add Telegram or Discord.
              </p>
              <div className="space-y-4">
                <div>
                  <Label>Telegram Bot Token <span className="text-muted font-normal">(optional)</span></Label>
                  <Input
                    type="password"
                    placeholder="1234567890:ABC…"
                    value={telegramToken}
                    onChange={setTelegramToken}
                  />
                  <Hint>Get from @BotFather on Telegram</Hint>
                </div>
                <div>
                  <Label>Discord Bot Token <span className="text-muted font-normal">(optional)</span></Label>
                  <Input
                    type="password"
                    placeholder="Your Discord bot token"
                    value={discordToken}
                    onChange={setDiscordToken}
                  />
                </div>
              </div>
            </Card>
          )}

          {step === 4 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">Review &amp; Launch</h2>
              <p className="text-[13px] text-muted mb-5">
                Save these files alongside <span className="font-mono text-blue">docker-compose.yml</span>, then run the command.
              </p>
              {loading && (
                <div className="text-center py-10 text-muted text-sm">Generating configuration…</div>
              )}
              {result && !result.error && (
                <div className="space-y-4">
                  <div className="p-3 rounded-lg bg-green/5 border border-green/20 text-green text-[13px] font-semibold text-center">
                    ✓ Configuration generated
                  </div>
                  {[
                    ['clawshield.env', result.clawshield_env, 'cs-env'],
                    ['agent.env', result.agent_env, 'agent-env'],
                    ['docker-compose.yml', result.compose_content, 'compose'],
                  ].map(([label, content, id]) => (
                    <div key={id}>
                      <Label>{label}</Label>
                      <CodeBlock id={id} content={content} />
                    </div>
                  ))}
                  <div>
                    <Label>Launch command</Label>
                    <CodeBlock id="launch" content={result.launch_command} />
                  </div>
                </div>
              )}
              {result?.error && (
                <div className="p-3 rounded-lg bg-red/10 border border-red/30 text-red text-sm">
                  {result.error}
                </div>
              )}
            </Card>
          )}
        </motion.div>
      </AnimatePresence>

      <Nav
        onBack={step === 1 ? onBack : () => setStep(step - 1)}
        onNext={next}
        nextLabel={step === TOTAL ? 'Open Dashboard' : 'Next'}
        nextDisabled={step === TOTAL && !result}
        loading={loading}
      />
      {step === TOTAL && result && !result.error && (
        <div className="text-center mt-3">
          <a href="/" className="text-blue text-[13px] hover:underline flex items-center justify-center gap-1">
            <ExternalLink className="w-3.5 h-3.5" /> Open Dashboard
          </a>
        </div>
      )}
    </div>
  )
}

// ─── Mode B: Build My Agent ───────────────────────────────────────────────────

const TOOL_OPTIONS = [
  {
    id: 'web_fetch',
    label: 'Search & read the web',
    desc: 'Browse websites to answer questions',
    security: 'HTTPS-only, scanned for injections before reaching the LLM.',
    default: true,
  },
  {
    id: 'memory',
    label: 'Remember things',
    desc: 'Save notes between conversations',
    security: 'Stored in workspace volume. Injected into context on each session.',
    default: false,
  },
  {
    id: 'file_read',
    label: 'Read your files',
    desc: 'Access files you share with it',
    security: 'Read-only access, scoped to workspace directory.',
    default: false,
  },
  {
    id: 'file_write',
    label: 'Write files',
    desc: 'Save documents and outputs',
    security: 'Write access scoped to workspace. Landlock enforces at kernel level.',
    default: false,
  },
]

function BuildAgentWizard({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [provider, setProvider] = useState('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [tools, setTools] = useState<string[]>(['web_fetch'])
  const [telegramToken, setTelegramToken] = useState('')
  const [expandedTool, setExpandedTool] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, string> | null>(null)
  const [loading, setLoading] = useState(false)
  const TOTAL = 5

  function toggleTool(id: string) {
    setTools((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    )
  }

  async function generate() {
    setLoading(true)
    try {
      const res = await fetch('/wizard/agent-builder/generate', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          provider,
          api_key: apiKey || 'CHANGEME',
          tools,
          telegram_bot_token: telegramToken,
        }),
      })
      setResult(await res.json())
    } catch {
      setResult({ error: 'Failed to generate config' })
    } finally {
      setLoading(false)
    }
  }

  function next() {
    if (step < TOTAL) setStep(step + 1)
    if (step === TOTAL - 1) generate()
  }

  return (
    <div>
      <StepIndicator current={step} total={TOTAL} />
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          variants={slideVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          {step === 1 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">Name &amp; Personality</h2>
              <p className="text-[13px] text-muted mb-5">
                Describe your agent like you're introducing it to a friend.
              </p>
              <div className="space-y-4">
                <div>
                  <Label>What should your agent be called?</Label>
                  <Input
                    placeholder="My Research Assistant"
                    value={name}
                    onChange={setName}
                  />
                </div>
                <div>
                  <Label>What does it do?</Label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="It helps me research topics, summarizes articles, and keeps notes on things I want to remember."
                    rows={3}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-[14px] text-text placeholder:text-muted outline-none focus:border-blue transition-colors font-sans resize-none"
                  />
                  <Hint>ClawShield generates the system prompt automatically. A security preamble is always prepended — your agent will never follow instructions embedded in web content.</Hint>
                </div>
              </div>
            </Card>
          )}

          {step === 2 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">Pick Your AI</h2>
              <p className="text-[13px] text-muted mb-5">
                Choose which AI powers your agent.
              </p>
              <div className="space-y-3 mb-4">
                {[
                  { value: 'anthropic', label: 'Claude (Anthropic)', sub: 'Best for writing and reasoning' },
                  { value: 'openai', label: 'GPT-4 (OpenAI)', sub: 'Familiar and versatile' },
                  { value: 'gemini', label: 'Gemini (Google)', sub: 'Great for research and search' },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setProvider(opt.value)}
                    className={`w-full flex items-center gap-3 p-4 rounded-lg border text-left transition-all ${
                      provider === opt.value
                        ? 'border-blue bg-blue/5'
                        : 'border-border bg-surface2/50 hover:border-border/80'
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                        provider === opt.value ? 'border-blue bg-blue' : 'border-muted'
                      }`}
                    />
                    <div>
                      <div className="font-semibold text-[14px]">{opt.label}</div>
                      <div className="text-[12px] text-muted">{opt.sub}</div>
                    </div>
                  </button>
                ))}
              </div>
              <div>
                <Label>API Key</Label>
                <Input
                  type="password"
                  placeholder="Paste your API key"
                  value={apiKey}
                  onChange={setApiKey}
                />
                <Hint>
                  Stored securely in clawshield.env. Think of this like a password that lets your agent use the AI service — it's never shared.
                </Hint>
              </div>
            </Card>
          )}

          {step === 3 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">What Can It Do?</h2>
              <p className="text-[13px] text-muted mb-5">
                Choose your agent's capabilities. Click any option to see security details.
              </p>
              <div className="space-y-2">
                {TOOL_OPTIONS.map((t) => (
                  <div key={t.id}>
                    <button
                      onClick={() => toggleTool(t.id)}
                      className={`w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-all ${
                        tools.includes(t.id)
                          ? 'border-green/40 bg-green/5'
                          : 'border-border bg-surface2/50 hover:border-border/80'
                      }`}
                    >
                      <div
                        className={`mt-0.5 w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                          tools.includes(t.id) ? 'border-green bg-green' : 'border-muted'
                        }`}
                      >
                        {tools.includes(t.id) && <Check className="w-2.5 h-2.5 text-bg" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-[14px]">{t.label}</div>
                        <div className="text-[12px] text-muted">{t.desc}</div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setExpandedTool(expandedTool === t.id ? null : t.id)
                        }}
                        className="text-[10px] text-blue hover:underline flex-shrink-0 mt-0.5"
                      >
                        security
                      </button>
                    </button>
                    <AnimatePresence>
                      {expandedTool === t.id && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden"
                        >
                          <div className="mx-1 mb-1 px-4 py-2.5 bg-blue/5 border-x border-b border-blue/20 rounded-b-lg text-[12px] text-muted">
                            {t.security}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {step === 4 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">How Do You Want to Talk to It?</h2>
              <p className="text-[13px] text-muted mb-5">
                Web chat is always available at localhost:8000.
              </p>
              <div className="mb-4 p-3 rounded-lg bg-green/5 border border-green/20 flex items-center gap-2 text-[13px] text-green font-medium">
                <Check className="w-4 h-4" /> Web chat — always on at localhost:8000
              </div>
              <div>
                <Label>Telegram Bot Token <span className="text-muted font-normal">(optional)</span></Label>
                <Input
                  type="password"
                  placeholder="1234567890:ABC…"
                  value={telegramToken}
                  onChange={setTelegramToken}
                />
                <Hint>Create a bot with @BotFather on Telegram and paste the token here.</Hint>
              </div>
            </Card>
          )}

          {step === 5 && (
            <Card>
              <h2 className="text-[17px] font-bold mb-1">Launch</h2>
              <p className="text-[13px] text-muted mb-5">
                Save these files and run the command to start your agent.
              </p>
              {loading && (
                <div className="text-center py-10 text-muted text-sm">Building your agent…</div>
              )}
              {result && !result.error && (
                <div className="space-y-4">
                  <div className="p-3 rounded-lg bg-green/5 border border-green/20 text-green text-[13px] font-semibold text-center">
                    ✓ Your agent is ready
                  </div>
                  {[
                    ['clawshield.env', result.clawshield_env, 'ab-cs-env'],
                    ['agent_config.json', result.agent_config, 'ab-config'],
                    ['docker-compose.yml', result.compose_content, 'ab-compose'],
                  ].map(([label, content, id]) => (
                    <div key={id}>
                      <Label>{label}</Label>
                      <CodeBlock id={id} content={content} />
                    </div>
                  ))}
                  <div>
                    <Label>Launch command</Label>
                    <CodeBlock id="ab-launch" content={result.launch_command} />
                  </div>
                </div>
              )}
              {result?.error && (
                <div className="p-3 rounded-lg bg-red/10 border border-red/30 text-red text-sm">
                  {result.error}
                </div>
              )}
            </Card>
          )}
        </motion.div>
      </AnimatePresence>

      <Nav
        onBack={step === 1 ? onBack : () => setStep(step - 1)}
        onNext={next}
        nextLabel={step === TOTAL && result ? 'Open Dashboard' : 'Next'}
        nextDisabled={
          (step === 1 && (!name.trim() || !description.trim())) ||
          (step === TOTAL && !result)
        }
        loading={loading}
      />
      {step === TOTAL && result && !result.error && (
        <div className="text-center mt-3">
          <a href="/" className="text-blue text-[13px] hover:underline flex items-center justify-center gap-1">
            <ExternalLink className="w-3.5 h-3.5" /> Open Dashboard
          </a>
        </div>
      )}
    </div>
  )
}

// ─── Mode selector ────────────────────────────────────────────────────────────

export function Wizard() {
  const [mode, setMode] = useState<Mode | null>(null)

  if (mode === 'connect') return <ConnectAgentWizard onBack={() => setMode(null)} />
  if (mode === 'build') return <BuildAgentWizard onBack={() => setMode(null)} />

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="text-center mb-10">
        <Shield className="w-12 h-12 text-blue mx-auto mb-4" strokeWidth={1.5} />
        <h1 className="text-2xl font-bold text-text">ClawShield Setup</h1>
        <p className="text-muted text-[14px] mt-2">
          Secure AI assistant platform — up and running in minutes
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => setMode('connect')}
          className="group flex flex-col items-start gap-3 p-6 rounded-xl border border-border bg-surface hover:border-blue/50 hover:bg-blue/5 transition-all text-left"
        >
          <div className="w-10 h-10 rounded-lg bg-surface2 flex items-center justify-center group-hover:bg-blue/10 transition-colors">
            <Zap className="w-5 h-5 text-muted group-hover:text-blue transition-colors" />
          </div>
          <div>
            <div className="font-bold text-[15px] text-text">Connect an Agent</div>
            <div className="text-[13px] text-muted mt-1">
              Wrap Mako, ZeroClaw, or any OpenClaw-compatible agent with ClawShield's security layer.
            </div>
          </div>
          <div className="flex items-center gap-1 text-blue text-[12px] font-medium mt-auto">
            Connect agent <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </button>

        <button
          onClick={() => setMode('build')}
          className="group flex flex-col items-start gap-3 p-6 rounded-xl border border-border bg-surface hover:border-purple/50 hover:bg-purple/5 transition-all text-left"
        >
          <div className="w-10 h-10 rounded-lg bg-surface2 flex items-center justify-center group-hover:bg-purple/10 transition-colors">
            <Shield className="w-5 h-5 text-muted group-hover:text-purple transition-colors" strokeWidth={1.5} />
          </div>
          <div>
            <div className="font-bold text-[15px] text-text">Build My Agent</div>
            <div className="text-[13px] text-muted mt-1">
              No setup required. Answer a few questions and ClawShield builds and secures your agent.
            </div>
          </div>
          <div className="flex items-center gap-1 text-purple text-[12px] font-medium mt-auto">
            Build my agent <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </button>
      </div>
    </motion.div>
  )
}
