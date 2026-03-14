"""ClawShield — FastAPI application entry point."""

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .chat import init_engine, router as chat_router
from .config import load_settings
from .engine import load_agent_config
from .events import SecurityEvent, bus
from .log_adapter import tail_audit_log
from .proxy import create_proxy_router
from .wizard import router as wizard_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ClawShield", version="1.0.0", docs_url=None, redoc_url=None)

settings = load_settings()

# Mount routers
app.include_router(chat_router)
app.include_router(wizard_router)
app.include_router(create_proxy_router(settings))

# Serve static files
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.on_event("startup")
async def startup() -> None:
    logger.info("ClawShield starting — mode=%s", settings.mode)

    # Initialize built-in engine if in builtin mode
    if settings.mode == "builtin":
        config = load_agent_config(settings.agent_config_path)
        init_engine(config)

    # Start audit log tailer in proxy mode (or always — it's a no-op if file doesn't exist)
    asyncio.create_task(tail_audit_log(settings.audit_log_path))

    bus.emit(SecurityEvent(
        type="LLM_REQUEST",
        severity="info",
        data={"note": "ClawShield started", "mode": settings.mode},
    ))


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    static_dir = Path(__file__).parent.parent.parent / "static"
    dashboard = static_dir / "dashboard.html"
    if dashboard.exists():
        return HTMLResponse(dashboard.read_text())
    return HTMLResponse("<h1>ClawShield</h1><p>Static files not found.</p>")


@app.get("/wizard-page", response_class=HTMLResponse)
async def wizard_page() -> HTMLResponse:
    static_dir = Path(__file__).parent.parent.parent / "static"
    wizard = static_dir / "wizard.html"
    if wizard.exists():
        return HTMLResponse(wizard.read_text())
    return HTMLResponse("<h1>Wizard not found</h1>")


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    """SSE endpoint — streams SecurityEvents to all connected dashboard tabs."""

    async def generate():
        # Send initial ping
        yield f"data: {json.dumps({'type': 'PING', 'severity': 'info', 'data': {}, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})}\n\n"
        async for event in bus.subscribe():
            if await request.is_disconnected():
                break
            from dataclasses import asdict
            yield f"data: {json.dumps(asdict(event))}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/stats")
async def stats() -> dict:
    return {
        "counts": bus.counts,
        "mode": settings.mode,
        "block_injections": settings.block_injections,
        "uptime_hint": "check /events for live data",
    }


@app.post("/settings/block-injections")
async def toggle_block_injections(enabled: bool = False) -> dict:
    settings.block_injections = enabled
    bus.emit(SecurityEvent(
        type="INJECTION_BLOCKED" if enabled else "LLM_REQUEST",
        severity="warn",
        data={"action": "block_mode_changed", "enabled": enabled},
    ))
    return {"block_injections": settings.block_injections}
