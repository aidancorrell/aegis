"""Tool implementations for the clawshield-agent runtime.

All tools are intentionally restrictive:
- web_fetch: HTTPS-only, blocks private/local IPs (SSRF protection)
- file_read / file_write: workspace-scoped only
- memory: appends to MEMORY.md in workspace
"""

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx

from audit import log_tool_call, log_tool_blocked

WORKSPACE = Path("/app/workspace")
MEMORY_FILE = WORKSPACE / "MEMORY.md"

# ─── SSRF guard ──────────────────────────────────────────────────────────────

_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",
}

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    if parsed.scheme != "https":
        return False, "Only HTTPS URLs are allowed"

    host = parsed.hostname or ""
    if not host:
        return False, "No host in URL"

    if host.lower() in _BLOCKED_HOSTS:
        return False, f"Host {host!r} is blocked"

    # Resolve and check IP
    try:
        addr = socket.gethostbyname(host)
        ip = ipaddress.ip_address(addr)
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                return False, f"Host resolves to private IP {addr}"
    except Exception:
        pass  # DNS failure — let httpx handle it

    return True, ""


# ─── Tool implementations ─────────────────────────────────────────────────────

async def web_fetch(url: str) -> str:
    safe, reason = _is_safe_url(url)
    if not safe:
        log_tool_blocked("web_fetch", {"url": url}, reason)
        return f"[BLOCKED: {reason}]"

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, max_redirects=3) as client:
            resp = await client.get(url, headers={"User-Agent": "ClawShield-Agent/1.0"})
        text = resp.text[:8000]  # cap at 8KB
        log_tool_call("web_fetch", {"url": url}, f"HTTP {resp.status_code}, {len(text)} chars")
        return text
    except httpx.TimeoutException:
        log_tool_blocked("web_fetch", {"url": url}, "Request timed out")
        return "[ERROR: request timed out]"
    except Exception as e:
        log_tool_blocked("web_fetch", {"url": url}, str(e))
        return f"[ERROR: {e}]"


def file_read(path: str) -> str:
    target = _resolve_workspace_path(path)
    if target is None:
        log_tool_blocked("file_read", {"path": path}, "Path outside workspace")
        return "[BLOCKED: path must be inside workspace]"

    if not target.exists():
        return f"[ERROR: file not found: {path}]"

    try:
        content = target.read_text(errors="replace")[:8000]
        log_tool_call("file_read", {"path": path}, f"{len(content)} chars")
        return content
    except Exception as e:
        return f"[ERROR: {e}]"


def file_write(path: str, content: str) -> str:
    target = _resolve_workspace_path(path)
    if target is None:
        log_tool_blocked("file_write", {"path": path}, "Path outside workspace")
        return "[BLOCKED: path must be inside workspace]"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        log_tool_call("file_write", {"path": path}, f"{len(content)} chars written")
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"[ERROR: {e}]"


def memory_read() -> str:
    if not MEMORY_FILE.exists():
        return "(no memories yet)"
    return MEMORY_FILE.read_text(errors="replace")[:4000]


def memory_write(note: str) -> str:
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_FILE, "a") as f:
            import time
            f.write(f"\n- [{time.strftime('%Y-%m-%d')}] {note}\n")
        log_tool_call("memory_write", {"note": note[:80]}, "saved")
        return "Memory saved."
    except Exception as e:
        return f"[ERROR: {e}]"


def _resolve_workspace_path(path: str) -> Path | None:
    try:
        target = (WORKSPACE / path).resolve()
        workspace = WORKSPACE.resolve()
        target.relative_to(workspace)  # raises ValueError if outside
        return target
    except (ValueError, Exception):
        return None


# ─── Anthropic tool schema ────────────────────────────────────────────────────

ALL_TOOL_DEFS = {
    "web_fetch": {
        "name": "web_fetch",
        "description": "Fetch content from an HTTPS URL. Returns the page text (max 8KB). Only public HTTPS URLs are allowed — local and private network addresses are blocked.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "HTTPS URL to fetch"}},
            "required": ["url"],
        },
    },
    "file_read": {
        "name": "file_read",
        "description": "Read a file from your workspace. Path is relative to workspace root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path"}},
            "required": ["path"],
        },
    },
    "file_write": {
        "name": "file_write",
        "description": "Write content to a file in your workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    "memory_read": {
        "name": "memory_read",
        "description": "Read your saved memories from previous conversations.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "memory_write": {
        "name": "memory_write",
        "description": "Save a note to your memory for future conversations.",
        "input_schema": {
            "type": "object",
            "properties": {"note": {"type": "string", "description": "What to remember"}},
            "required": ["note"],
        },
    },
}


async def execute_tool(name: str, args: dict) -> str:
    match name:
        case "web_fetch":
            return await web_fetch(args.get("url", ""))
        case "file_read":
            return file_read(args.get("path", ""))
        case "file_write":
            return file_write(args.get("path", ""), args.get("content", ""))
        case "memory_read":
            return memory_read()
        case "memory_write":
            return memory_write(args.get("note", ""))
        case _:
            return f"[ERROR: unknown tool {name!r}]"
