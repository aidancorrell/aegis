"""Web chat endpoint — powered by the built-in engine."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .engine import AgentConfig, BuiltinEngine

logger = logging.getLogger(__name__)

router = APIRouter()

_engine: BuiltinEngine | None = None


def init_engine(config: AgentConfig) -> None:
    global _engine
    _engine = BuiltinEngine(config)
    logger.info("BuiltinEngine initialized with provider=%s", config.provider)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Agent engine not initialized. Complete wizard setup first.")
    reply = await _engine.run(req.message, req.session_id)
    return ChatResponse(reply=reply)
