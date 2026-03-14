"""Audit log tailer — reads Mako's JSON-lines audit.log and emits SecurityEvents.

Runs as an asyncio background task. Uses polling fallback (inotify optional).
Parses Mako's audit entry format:
  {"timestamp": "...", "tool": "...", "args": {...}, "result": "...", "error": "..."}
"""

import asyncio
import json
import logging
from pathlib import Path

from .events import SecurityEvent, bus

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 0.5  # seconds


async def tail_audit_log(log_path: str) -> None:
    """Tail the audit log and emit events. Runs forever as a background task."""
    path = Path(log_path)
    logger.info("Audit log tailer starting: %s", path)

    # Wait for the file to appear
    while not path.exists():
        await asyncio.sleep(2)
        logger.debug("Waiting for audit log: %s", path)

    with open(path) as f:
        # Seek to end — don't replay history on startup
        f.seek(0, 2)

        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            _emit_from_entry(entry)


def _emit_from_entry(entry: dict) -> None:
    """Convert a Mako audit log entry to a SecurityEvent."""
    tool = entry.get("tool", "unknown")
    args = entry.get("args", {})
    error = entry.get("error")
    result = entry.get("result", "")
    timestamp = entry.get("timestamp", "")

    if error:
        # Tool was blocked or failed
        bus.emit(SecurityEvent(
            type="TOOL_BLOCKED",
            severity="high",
            data={
                "tool": tool,
                "args": args,
                "error": error[:300],
                "source": "audit_log",
            },
            timestamp=timestamp or _now(),
        ))
    else:
        bus.emit(SecurityEvent(
            type="TOOL_CALL",
            severity="info",
            data={
                "tool": tool,
                "args": args,
                "result_snippet": (result or "")[:200],
                "source": "audit_log",
            },
            timestamp=timestamp or _now(),
        ))


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
