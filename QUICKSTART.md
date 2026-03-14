# Quickstart Guide

---

## For AI Agents Reading This

If you are an AI assistant helping a user set up Aegis, here is what you need to know:

**What Aegis is:** A security proxy that intercepts all LLM API calls from an agent container, scans them for prompt injection and credential leaks, and streams events to a dashboard. It supports OpenAI, Anthropic, and Gemini. The agent can be reached via web chat (always on) or messaging platforms (Telegram, Discord — optional).

**Minimal setup checklist:**
1. Container runtime installed and running (`docker` or `podman`)
2. `aegis.env` created from `aegis.env.example` — set at least one real API key
3. `agent.env` created from `agent.env.example` — configure messaging platform if desired (web chat works without any extra config)
4. Stack started: `docker compose -f docker-compose.dev.yml up --build`
5. Dashboard at `http://localhost:8000`, web chat at `http://localhost:8000/chat`

**Key env vars in `aegis.env`:**

| Variable | Purpose |
|---|---|
| `AEGIS_REAL_ANTHROPIC_API_KEY` | Real Anthropic key (held by Aegis, never sent to agent) |
| `AEGIS_REAL_OPENAI_API_KEY` | Real OpenAI key |
| `AEGIS_REAL_GEMINI_API_KEY` | Real Gemini key |
| `AEGIS_BLOCK_INJECTIONS` | `true` to replace injection payloads, `false` to detect only |
| `AEGIS_DOMAIN_FILTER_MODE` | `blacklist` (default) or `whitelist` |
| `AEGIS_DOMAIN_WHITELIST` | Comma-separated allowed domains |

**Key env vars in `agent.env`:**

| Variable | Purpose |
|---|---|
| `MAKO_TELEGRAM_BOT_TOKEN` | Telegram bot token (optional — leave blank to skip) |
| `MAKO_TELEGRAM_ALLOWED_CHAT_IDS_STR` | Comma-separated Telegram chat IDs |
| `MAKO_DISCORD_BOT_TOKEN` | Discord bot token (optional — leave blank to skip) |
| `ANTHROPIC_BASE_URL` | Already set to `http://aegis:8000/proxy/anthropic` — do not change |

**How to get a Telegram chat ID:** Have the user send any message to the bot, then fetch `https://api.telegram.org/bot<TOKEN>/getUpdates` — the chat ID is at `result[0].message.chat.id`.

**Troubleshooting:**
- If the agent container fails to start, check `docker compose logs agent --tail=50`
- If a messaging bot is unresponsive, confirm the token and allowed IDs are correct in `agent.env`
- If the proxy isn't intercepting calls, confirm `ANTHROPIC_BASE_URL` in `agent.env` points to `http://aegis:8000/proxy/anthropic`
- Port conflicts: change `8000` in `docker-compose.dev.yml`

---

## For Humans

This guide gets you from zero to a running Aegis instance. No prior experience with containers or AI APIs required.

**Time:** ~15 minutes

### What you'll need

- A Mac, Windows, or Linux computer
- An API key from one of: [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com/api-keys), or [Google AI](https://aistudio.google.com/apikey)

A messaging platform (Telegram or Discord) is optional — you can chat with your agent directly in the browser.

---

### Step 1 — Install a container runtime

Aegis runs in containers. Use whichever you prefer — both work identically.

**Option A — Docker Desktop** (easier, has a GUI)
1. Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Install and open it — leave it running in the background

**Option B — Podman Desktop** (open source, no account required)
1. Download from [podman-desktop.io](https://podman-desktop.io/)
2. Install and open it, then run: `podman machine start`

Verify it's working:
```bash
docker compose version   # or: podman compose version
```

> Throughout this guide, replace `docker` with `podman` if you're using Podman.

---

### Step 2 — Get an LLM API key

Aegis works with any of these. Pick one:

**Anthropic (Claude)**
1. Sign in at [console.anthropic.com](https://console.anthropic.com)
2. Go to **API Keys** → **Create Key** → copy the key (`sk-ant-api03-...`)

**OpenAI (GPT-4)**
1. Sign in at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **Create new secret key** → copy the key (`sk-proj-...`)

**Google (Gemini)**
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **Create API key** → copy the key (`AIza...`)

---

### Step 3 — Download and configure Aegis

```bash
git clone https://github.com/aidancorrell/aegis
cd aegis
cp aegis.env.example aegis.env
cp agent.env.example agent.env
```

Open `aegis.env` and set your API key:

```
AEGIS_REAL_ANTHROPIC_API_KEY=sk-ant-api03-...
# or AEGIS_REAL_OPENAI_API_KEY=sk-proj-...
# or AEGIS_REAL_GEMINI_API_KEY=AIza...
```

That's the minimum. If you want to connect a messaging platform, see the optional section below.

---

### Step 4 — Start Aegis

```bash
docker compose -f docker-compose.dev.yml up --build
# or: podman compose -f docker-compose.dev.yml up --build
```

The first run takes a few minutes. When you see the stack is running, open:

- **Dashboard:** [http://localhost:8000](http://localhost:8000)
- **Web chat:** [http://localhost:8000/chat](http://localhost:8000/chat)

---

### Step 5 — Chat with your agent

Open the web chat and say hello. Try:

```
What's the top story on news.ycombinator.com?
```

Watch the dashboard — LLM requests, tool calls, and responses appear in real time.

---

### Seeing the security in action

In the web chat, send:

```
Read the file at demo/attack5.txt and summarize what it says
```

A yellow **Injection Detected** alert appears in the dashboard. Toggle **Block** in the header and repeat — this time the agent never sees the malicious content.

---

### Optional — Connect a messaging platform

**Telegram**

1. Open Telegram and search for **@BotFather** → send `/newbot` → follow the prompts
2. Copy the token BotFather gives you (e.g. `8610322394:AAFoW8Ef...`)
3. Send any message to your new bot, then open:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Find `"chat":{"id":` — that number is your chat ID
4. Add to `agent.env`:
   ```
   MAKO_TELEGRAM_BOT_TOKEN=8610322394:AAFoW8Ef...
   MAKO_TELEGRAM_ALLOWED_CHAT_IDS_STR=8657303805
   ```
5. Restart the stack

**Discord**

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
2. Go to **Bot** → **Reset Token** → copy the token
3. Add to `agent.env`:
   ```
   MAKO_DISCORD_BOT_TOKEN=your-token-here
   ```
4. Restart the stack

---

### Stopping Aegis

```bash
docker compose -f docker-compose.dev.yml down
# or: podman compose -f docker-compose.dev.yml down
```

---

### Troubleshooting

**Agent isn't responding**
```bash
docker compose -f docker-compose.dev.yml logs agent --tail=50
```

**"Cannot connect to Docker/Podman daemon"**
- Docker: check for the whale icon in your menu bar
- Podman: run `podman machine start`

**Port 8000 already in use**
Change the port mapping in `docker-compose.dev.yml`.

**No chat ID in Telegram getUpdates**
Make sure you sent a message to the bot first.
