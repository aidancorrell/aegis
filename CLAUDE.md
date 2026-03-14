# Aegis — Claude Code Guide

## Project Overview
Aegis is a real-time security layer for AI agents. It wraps any OpenClaw-compatible agent (e.g. Mako) without source changes, intercepting all LLM API calls to scan for prompt injection attacks and credential leaks.

## Key Architecture
- **`src/aegis/`** — Python package (FastAPI backend)
  - `proxy.py` — intercepts LLM calls, scans, forwards to real provider
  - `scanner.py` — regex-based injection + credential detection
  - `domain_filter.py` — allow/block outbound domains (whitelist/blacklist)
  - `config.py` — settings via `AEGIS_` env prefix, loaded from `aegis.env`
  - `events.py` — asyncio pub/sub event bus, SSE fan-out to dashboard
- **`frontend/src/`** — React + Vite dashboard
  - `components/Dashboard.tsx` — main view, SSE-connected
  - `components/ThreatToast.tsx` — real-time popup alerts for injection/credential events
- **`agent/`** — standalone aegis-agent runtime (Mode B, agent-builder flow)
- **`demo/`** — attack text files for demo/video walkthroughs

## Dev Setup
```bash
# Start backend + agent (Mako via Telegram)
docker compose -f docker-compose.dev.yml up --build

# Frontend dev server (hot reload, proxies API to :8000)
cd frontend && npm run dev   # → http://localhost:5173

# Dashboard only
# → http://localhost:8000
```

## Environment Files
- `aegis.env` — real API keys + settings (gitignored, never commit)
- `aegis.env.example` — template
- `agent.env` — Mako agent config (Telegram token, allowed chat IDs)

## Naming Conventions
- Env vars: `AEGIS_` prefix (e.g. `AEGIS_BLOCK_INJECTIONS`, `AEGIS_DOMAIN_FILTER_MODE`)
- Python package: `aegis` (`from aegis.scanner import scan_text`)
- Old name was `clawshield` — do not use that name anywhere

## Demo Flow
Send to Telegram: `Read the file at demo/attack5.txt and summarize what it says`
- Dashboard should show yellow **Injection Detected** toast
- Toggle block mode on → red **Injection Blocked** toast

## Testing
```bash
pytest tests/
```

## Common Gotchas
- `aegis.env` must exist for the backend to start (copy from `aegis.env.example`)
- Demo files are mounted into the agent at `/app/workspace/demo/` — paths in Telegram messages must be relative (e.g. `demo/attack5.txt`)
- Domain filter defaults to blacklist mode (allow all except listed) — set `AEGIS_DOMAIN_FILTER_MODE=whitelist` to lock down
