"""ClawShield — FastAPI application entry point."""

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .events import SecurityEvent, bus
from . import hardening
from .log_adapter import tail_audit_log
from .proxy import create_proxy_router
from .wizard import router as wizard_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ClawShield", version="1.0.0", docs_url=None, redoc_url=None)

settings = load_settings()

# Mount routers
app.include_router(wizard_router)
app.include_router(create_proxy_router(settings))

# Serve React build assets (Vite outputs to static/dist/assets)
_dist_dir = Path(__file__).parent.parent.parent / "static" / "dist"
if _dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist_dir / "assets")), name="assets")


@app.on_event("startup")
async def startup() -> None:
    logger.info("ClawShield starting — mode=proxy (Mako)")

    # Apply kernel-level hardening (Landlock on Linux/Docker, Seatbelt on macOS native)
    hardening.status = hardening.apply("/tmp", "/tmp")

    # Tail Mako's audit log from shared volume
    asyncio.create_task(tail_audit_log(settings.audit_log_path))

    bus.emit(SecurityEvent(
        type="LLM_REQUEST",
        severity="info",
        data={"note": "ClawShield started", "mode": "proxy"},
    ))


def _react_index() -> HTMLResponse:
    dist = Path(__file__).parent.parent.parent / "static" / "dist" / "index.html"
    if dist.exists():
        return HTMLResponse(dist.read_text())
    return HTMLResponse(
        "<h1>ClawShield</h1><p>Run <code>cd frontend && npm run build</code> to build the UI.</p>"
    )


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return _react_index()


@app.get("/wizard-page", response_class=HTMLResponse)
async def wizard_page() -> HTMLResponse:
    return _react_index()


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    """SSE endpoint — streams SecurityEvents to all connected dashboard tabs."""

    async def generate():
        yield "data: " + json.dumps({'type': 'PING', 'severity': 'info', 'data': {}, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + "\n\n"
        async for event in bus.subscribe():
            if await request.is_disconnected():
                break
            from dataclasses import asdict
            yield "data: " + json.dumps(asdict(event)) + "\n\n"

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
    from dataclasses import asdict
    return {
        "counts": bus.counts,
        "mode": "proxy",
        "block_injections": settings.block_injections,
        "hardening": asdict(hardening.status),
        "uptime_hint": "check /events for live data",
    }


@app.get("/hardening")
async def hardening_status() -> dict:
    from dataclasses import asdict
    return asdict(hardening.status)


_AGENT_BASE = "http://agent:8001"
_STRIP = {"host", "content-length", "transfer-encoding", "connection"}


@app.api_route("/agent-chat/{path:path}", methods=["GET", "POST"])
async def agent_chat_proxy(request: Request, path: str) -> Response:
    """Transparent proxy to the clawshield-agent web chat (port 8001)."""
    url = f"{_AGENT_BASE}/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _STRIP}
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                params=dict(request.query_params),
                headers=headers,
                content=body,
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding"}},
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        return Response(content='{"error":"agent not running"}', status_code=503, media_type="application/json")


@app.post("/settings/block-injections")
async def toggle_block_injections(enabled: bool = False) -> dict:
    settings.block_injections = enabled
    bus.emit(SecurityEvent(
        type="INJECTION_BLOCKED" if enabled else "LLM_REQUEST",
        severity="warn",
        data={"action": "block_mode_changed", "enabled": enabled},
    ))
    return {"block_injections": settings.block_injections}
