# Aegis 🛡

**Real-time security layer for AI agents — catches and blocks prompt injection attacks before they reach the LLM.**

Aegis sits between your AI agent and the internet. Every LLM call passes through it, every tool result gets scanned, and every attack attempt shows up live on a dashboard. If a malicious webpage tries to hijack your agent mid-task ([ClawJacked](https://www.wired.com/story/claude-claude-mcp-prompt-injection/)), Aegis catches it before the LLM ever sees it.

---

## Quick Start

**Have Docker and an Anthropic API key?**

```bash
git clone https://github.com/aidancorrell/aegis
cd aegis
cp aegis.env.example aegis.env   # add your AEGIS_REAL_ANTHROPIC_API_KEY
cp agent.env.example agent.env   # add your Telegram bot token + chat ID
docker compose -f docker-compose.dev.yml up --build
```

Open `http://localhost:8000` — dashboard is live.

**New to this?** See [QUICKSTART.md](QUICKSTART.md) for a step-by-step walkthrough including Docker setup, getting an API key, and creating a Telegram bot.

---

## How It Works

Aegis intercepts every LLM API call your agent makes via a single environment variable:

```
ANTHROPIC_BASE_URL=http://aegis:8000/proxy/anthropic
```

The agent holds only a dummy API key — the real key lives in Aegis only. Even a fully compromised agent cannot make direct LLM calls.

```
 User (Telegram/Web)
        │
        ▼
 ┌─────────────┐        ┌──────────────────┐
 │    Agent    │──────▶ │  Aegis Proxy     │──▶ Anthropic / OpenAI / Gemini
 │   (Mako)   │        │  scans every     │
 └─────────────┘        │  request         │
                        └────────┬─────────┘
                                 │ events
                        ┌────────▼─────────┐
                        │   Dashboard      │
                        │  localhost:8000  │
                        └──────────────────┘
```

---

## Security Features

### Injection Detection & Blocking

Every tool result (web fetches, file reads) is scanned for prompt injection before the LLM sees it. When blocking is on, the malicious payload is replaced with `[BLOCKED: prompt injection detected by Aegis]`.

Patterns detected include: `ignore previous instructions`, `you are now`, `DAN mode`, exfiltration attempts, token-style injections (`<|system|>`, `[[...]]`), and more.

### Credential Leak Detection

Responses and tool results are scanned for API keys, tokens, and secrets — OpenAI, Anthropic, AWS, Google, GitHub, and JWT patterns. Detected credentials in responses are redacted before they reach the agent.

### Domain Filter

Whitelist or blacklist outbound domains. Set `AEGIS_DOMAIN_FILTER_MODE=whitelist` and `AEGIS_DOMAIN_WHITELIST=api.anthropic.com,...` to lock the agent to approved endpoints only.

### Kernel Hardening

| Platform | Mechanism | Effect |
|---|---|---|
| Linux / Docker | Landlock | OS-level write restriction — only `/tmp` is writable |
| macOS | Seatbelt | `no-write-except-temporary` kernel profile |

### Container Hardening

Read-only filesystem, no Linux capabilities (`cap_drop: ALL`), no-new-privileges, seccomp syscall filter, 256MB memory cap.

### Real-Time Dashboard

Every security event streams live via SSE:

| Event | What it means |
|---|---|
| `INJECTION_PROBE` | Injection pattern found in a tool result |
| `INJECTION_BLOCKED` | Payload replaced before reaching the LLM |
| `CREDENTIAL_LEAK` | Credential pattern detected in content |
| `DOMAIN_BLOCKED` | Outbound request blocked by domain filter |
| `TOOL_BLOCKED` | Agent's own security guard blocked a tool call |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  aegis container                                             │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  LLM Proxy  │   │  Event Bus   │   │   Dashboard UI   │  │
│  │  /proxy/*   │──▶│  (asyncio)   │──▶│  localhost:8000  │  │
│  └──────┬──────┘   └──────────────┘   └──────────────────┘  │
│         │                 ▲                                   │
│  ┌──────▼──────┐   ┌──────┴──────┐                          │
│  │   Scanner   │   │ Log Adapter │                           │
│  │  injection  │   │ (audit.log) │                           │
│  │  + cred     │   └─────────────┘                           │
│  └─────────────┘                                             │
└──────────────────────────────────────────────────────────────┘
           ▲ ANTHROPIC_BASE_URL intercepts all LLM calls
┌──────────────────────────────────────────────────────────────┐
│  agent container (Mako)                                      │
│  Telegram / Web  →  ReAct loop  →  Tools                    │
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
src/aegis/
├── main.py          # FastAPI app, routes, startup
├── config.py        # Settings — AEGIS_* env vars, loaded from aegis.env
├── proxy.py         # LLM proxy — OpenAI, Anthropic, Gemini
├── scanner.py       # Injection + credential detection (regex, no LLM)
├── domain_filter.py # Domain allow/block filtering
├── events.py        # SecurityEventBus — asyncio pub/sub, SSE fan-out
├── log_adapter.py   # Tails Mako's audit.log from shared Docker volume
├── hardening.py     # Landlock + Seatbelt kernel hardening
└── wizard.py        # Setup wizard API

frontend/src/        # React + Vite dashboard
demo/                # Attack files for demo walkthroughs
```

---

## Environment Variables

All prefixed `AEGIS_`. Set in `aegis.env`.

| Variable | Default | Description |
|---|---|---|
| `AEGIS_REAL_ANTHROPIC_API_KEY` | — | Your real Anthropic key (never sent to agent) |
| `AEGIS_REAL_OPENAI_API_KEY` | — | Your real OpenAI key |
| `AEGIS_REAL_GEMINI_API_KEY` | — | Your real Gemini key |
| `AEGIS_BLOCK_INJECTIONS` | `true` | Replace injection payloads before forwarding |
| `AEGIS_DOMAIN_FILTER_MODE` | `blacklist` | `blacklist` or `whitelist` |
| `AEGIS_DOMAIN_WHITELIST` | — | Comma-separated allowed domains |
| `AEGIS_DOMAIN_BLACKLIST` | — | Comma-separated blocked domains |

---

## Roadmap

- [ ] **`install.sh`** — single `curl | bash` that pulls images and opens the wizard
- [ ] **Agent Builder** — build a personal AI assistant through the UI, no Mako required ([spec](docs/agent-builder.md))
- [ ] **Gemini proxy** — TLS termination for providers that don't support `base_url` override
- [ ] **VPS deploy** — wizard generates SSH deploy commands for remote servers
