"""Web chat endpoint for the aegis-agent runtime."""

import anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from loop import run_turn

# Per-session conversation history (in-memory, resets on restart)
_history: list[dict] = []


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


def build_app(config: dict, client: anthropic.AsyncAnthropic) -> FastAPI:
    app = FastAPI(title=config["name"], docs_url=None, redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        global _history
        reply, _history = await run_turn(
            client=client,
            model=config["model"],
            system_prompt=config["system_prompt"],
            tool_names=config.get("tools", []),
            history=_history[-40:],
            user_message=req.message,
        )
        return ChatResponse(response=reply)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent": config["name"]}

    return app
