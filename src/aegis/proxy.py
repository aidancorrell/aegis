"""LLM API Proxy — transparent interception for OpenAI, Anthropic, and Gemini.

When an agent container has extra_hosts DNS override pointing these providers to
Aegis's IP, all LLM calls land here. Aegis:
  1. Emits LLM_REQUEST event
  2. Scans messages for injection patterns
  3. Strips the agent's dummy API key, injects the real key
  4. Forwards to the real provider
  5. Emits LLM_RESPONSE event
  6. Returns the response transparently
"""

import json
import logging
import time

import httpx
from fastapi import APIRouter, Request, Response

from .config import Settings
from .events import SecurityEvent, bus
from .scanner import scan_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy")

# Real provider base URLs
_OPENAI_BASE = "https://api.openai.com"
_ANTHROPIC_BASE = "https://api.anthropic.com"
_GEMINI_BASE = "https://generativelanguage.googleapis.com"

# Headers to strip when forwarding (hop-by-hop + auth)
_STRIP_HEADERS = {"host", "content-length", "transfer-encoding", "authorization",
                  "x-goog-api-key", "connection", "keep-alive"}


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=120, follow_redirects=True)


async def _proxy_request(
    request: Request,
    target_base: str,
    real_api_key: str,
    provider: str,
    settings: Settings,
) -> Response:
    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except Exception:
        body = {}

    messages = body.get("messages", body.get("contents", []))
    tool_count = len(body.get("tools", body.get("tool_config", {}).get("function_calling_config", {}).get("allowed_function_names", [])))

    # Emit LLM_REQUEST
    last_user_msg = ""
    for m in reversed(messages):
        c = m.get("content", "")
        if isinstance(c, str) and m.get("role") in ("user", "human"):
            last_user_msg = c[:200]
            break
        elif isinstance(c, list):
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    last_user_msg = block.get("text", "")[:200]
                    break

    bus.emit(SecurityEvent(
        type="LLM_REQUEST",
        severity="info",
        data={
            "provider": provider,
            "message_count": len(messages),
            "tool_count": tool_count,
            "last_user_message": last_user_msg,
        },
    ))

    # Scan for injections
    hits = scan_messages(messages)
    injection_found = any(h.has_injection for h in hits)
    cred_found = any(h.has_credential for h in hits)

    if hits:
        severity = "critical" if injection_found else "high"
        event_type = "INJECTION_PROBE" if injection_found else "CREDENTIAL_LEAK"
        bus.emit(SecurityEvent(
            type=event_type,
            severity=severity,
            data={
                "provider": provider,
                "patterns": [p for h in hits for p in h.matched_patterns],
                "snippet": hits[0].snippet[:300],
            },
        ))

    # Block injections if configured
    if injection_found and settings.block_injections:
        # Replace tool result content with blocked message
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "tool" and isinstance(content, str):
                for pattern_group in hits:
                    if pattern_group.has_injection:
                        msg["content"] = "[BLOCKED: prompt injection detected by Aegis]"
                        break
            elif role == "user" and isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        block["content"] = "[BLOCKED: prompt injection detected by Aegis]"

        body["messages"] = messages
        body_bytes = json.dumps(body).encode()

        bus.emit(SecurityEvent(
            type="INJECTION_BLOCKED",
            severity="critical",
            data={"provider": provider, "action": "tool_result_sanitized"},
        ))

    # Build forwarded headers — strip auth, add real key
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _STRIP_HEADERS
    }
    forward_headers["content-length"] = str(len(body_bytes))

    if provider == "openai":
        forward_headers["authorization"] = f"Bearer {real_api_key}"
    elif provider == "anthropic":
        forward_headers["x-api-key"] = real_api_key
        forward_headers["anthropic-version"] = request.headers.get("anthropic-version", "2023-06-01")
    elif provider == "gemini":
        forward_headers["x-goog-api-key"] = real_api_key

    # Build target URL
    path = request.url.path.removeprefix(f"/proxy/{provider}")
    if provider == "gemini":
        # Gemini uses query param for key too — remove it, we use header
        target_url = f"{target_base}{path}"
        # Preserve query params (model name, etc.) but drop key param
        query_params = {k: v for k, v in request.query_params.items() if k != "key"}
    else:
        target_url = f"{target_base}{path}"
        query_params = dict(request.query_params)

    start = time.monotonic()
    async with _make_client() as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            params=query_params,
            headers=forward_headers,
            content=body_bytes,
        )
    latency_ms = int((time.monotonic() - start) * 1000)

    bus.emit(SecurityEvent(
        type="LLM_RESPONSE",
        severity="info",
        data={
            "provider": provider,
            "status": resp.status_code,
            "latency_ms": latency_ms,
        },
    ))

    # Check response for credential leaks
    if cred_found:
        bus.emit(SecurityEvent(
            type="CREDENTIAL_LEAK",
            severity="high",
            data={"provider": provider, "note": "potential credential in tool result"},
        ))

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items()
                 if k.lower() not in {"content-encoding", "transfer-encoding"}},
        media_type=resp.headers.get("content-type"),
    )


def create_proxy_router(settings: Settings) -> APIRouter:
    """Create the proxy router with settings bound via closure."""

    @router.api_route("/openai/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def openai_proxy(request: Request, path: str) -> Response:
        return await _proxy_request(request, _OPENAI_BASE, settings.real_openai_api_key, "openai", settings)

    @router.api_route("/anthropic/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def anthropic_proxy(request: Request, path: str) -> Response:
        return await _proxy_request(request, _ANTHROPIC_BASE, settings.real_anthropic_api_key, "anthropic", settings)

    @router.api_route("/gemini/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def gemini_proxy(request: Request, path: str) -> Response:
        return await _proxy_request(request, _GEMINI_BASE, settings.real_gemini_api_key, "gemini", settings)

    return router
