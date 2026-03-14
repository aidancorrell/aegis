"""clawshield-agent — minimal secure agent runtime.

Reads agent_config.json, starts the LLM client, and launches channels
(web chat always on, Telegram optional).

All LLM calls route through ClawShield proxy via ANTHROPIC_BASE_URL env var.
All tool calls are logged to /app/audit/audit.log (shared volume).
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import anthropic
import uvicorn

from web import build_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(os.getenv("AGENT_CONFIG_PATH", "/app/agent_config.json"))


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"agent_config.json not found at {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text())


async def run_telegram(config: dict, client: anthropic.AsyncAnthropic) -> None:
    """Simple long-poll Telegram loop."""
    import httpx
    from loop import run_turn

    token = config.get("channels", {}).get("telegram_token", "")
    if not token:
        return

    logger.info("Telegram channel starting")
    base = f"https://api.telegram.org/bot{token}"
    offset = 0
    # Per-chat conversation history
    histories: dict[int, list[dict]] = {}

    async with httpx.AsyncClient(timeout=35) as http:
        while True:
            try:
                resp = await http.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 30})
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "").strip()
                    if not chat_id or not text or text.startswith("/"):
                        continue

                    history = histories.get(chat_id, [])
                    reply, history = await run_turn(
                        client=client,
                        model=config["model"],
                        system_prompt=config["system_prompt"],
                        tool_names=config.get("tools", []),
                        history=history[-40:],  # keep last 20 turns
                        user_message=text,
                    )
                    histories[chat_id] = history

                    await http.post(f"{base}/sendMessage", json={"chat_id": chat_id, "text": reply})
            except Exception as e:
                logger.warning("Telegram error: %s", e)
                await asyncio.sleep(5)


async def main() -> None:
    config = load_config()
    logger.info("Starting agent: %s (provider=%s, model=%s)", config["name"], config["provider"], config["model"])

    # The Anthropic SDK reads ANTHROPIC_BASE_URL from env — pointing to ClawShield proxy
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY"))

    app = build_app(config, client)

    # Start Telegram in background if configured
    asyncio.create_task(run_telegram(config, client))

    # Web chat always on
    cfg = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="warning")
    server = uvicorn.Server(cfg)
    logger.info("Web chat at http://localhost:8001/chat")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
