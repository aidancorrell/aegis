# Quickstart Guide

This guide gets you from zero to a running Aegis instance with a Telegram-connected AI agent. No prior experience with Docker or AI APIs required.

**Time:** ~20 minutes

---

## What you'll need

- A Mac, Windows, or Linux computer
- An [Anthropic account](https://console.anthropic.com) (for Claude API access)
- A Telegram account (for chatting with your agent)

---

## Step 1 — Install Docker Desktop

Docker runs Aegis and your agent in isolated containers. It's the only thing you need to install.

1. Download **Docker Desktop** from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Install and open it — you should see a whale icon in your menu bar
3. Leave it running in the background

---

## Step 2 — Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign in
2. Click **API Keys** in the left sidebar
3. Click **Create Key**, give it a name like "aegis", and copy the key

It looks like: `sk-ant-api03-...`

Keep this somewhere safe — you'll paste it in a moment.

---

## Step 3 — Create a Telegram bot

Your agent will live in Telegram. You need to create a bot for it.

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. `My Aegis Agent`) and a username ending in `bot` (e.g. `my_aegis_bot`)
4. BotFather gives you a **token** — copy it. It looks like `8610322394:AAFoW8Ef...`

Next, get your Telegram chat ID:

1. Send any message to your new bot
2. Open this URL in your browser, replacing `<TOKEN>` with your bot token:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Find `"chat":{"id":` in the response — that number is your chat ID (e.g. `8657303805`)

---

## Step 4 — Download and configure Aegis

Open a terminal and run:

```bash
git clone https://github.com/aidancorrell/aegis
cd aegis
```

**Configure Aegis** (holds your real API key):

```bash
cp aegis.env.example aegis.env
```

Open `aegis.env` in a text editor and set:

```
AEGIS_REAL_ANTHROPIC_API_KEY=sk-ant-api03-...   ← your key from Step 2
```

**Configure the agent** (Telegram connection):

```bash
cp agent.env.example agent.env
```

Open `agent.env` and set:

```
MAKO_TELEGRAM_BOT_TOKEN=8610322394:AAFoW8Ef...   ← your bot token from Step 3
MAKO_TELEGRAM_ALLOWED_CHAT_IDS_STR=8657303805    ← your chat ID from Step 3
```

---

## Step 5 — Start Aegis

```bash
docker compose -f docker-compose.dev.yml up --build
```

The first run takes a few minutes to download and build everything. When you see:

```
Telegram bot is running
```

you're good to go.

---

## Step 6 — Open the dashboard

Open [http://localhost:8000](http://localhost:8000) in your browser.

You'll see the Aegis security dashboard — a live feed of everything your agent does.

---

## Step 7 — Chat with your agent

Open Telegram and send a message to your bot:

```
Hello!
```

It should reply within a few seconds.

Try asking it to fetch a webpage:

```
What's the top story on news.ycombinator.com?
```

Watch the dashboard — you'll see the LLM request, tool calls, and response appear in real time.

---

## Seeing the security in action

The demo folder contains files that simulate prompt injection attacks — malicious instructions hidden in content your agent might read.

Send this to your bot:

```
Read the file at demo/attack5.txt and summarize what it says
```

Watch the dashboard — a yellow **Injection Detected** alert should appear.

To see Aegis block the attack (not just detect it), click the **Block** toggle in the dashboard header, then repeat. This time the agent never sees the malicious content.

---

## Stopping Aegis

Press `Ctrl+C` in the terminal, or run:

```bash
docker compose -f docker-compose.dev.yml down
```

---

## Troubleshooting

**Bot isn't responding**

Check the logs:
```bash
docker compose -f docker-compose.dev.yml logs agent --tail=50
```

**"Cannot connect to Docker daemon"**

Make sure Docker Desktop is running (whale icon in menu bar).

**Port 8000 already in use**

Something else is using port 8000. Stop that service, or change the port in `docker-compose.dev.yml`.

**No chat ID in getUpdates response**

Make sure you sent a message to your bot first — Telegram doesn't return updates until the bot has received at least one message.
