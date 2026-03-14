"""SecurityEventBus — asyncio-based pub/sub for all security events."""

import asyncio
import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import AsyncGenerator


@dataclass
class SecurityEvent:
    type: str
    # Types: LLM_REQUEST | LLM_RESPONSE | TOOL_CALL | TOOL_BLOCKED |
    #        INJECTION_PROBE | INJECTION_BLOCKED | CREDENTIAL_LEAK | RATE_LIMIT_HIT
    severity: str  # info | warn | high | critical
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_sse(self) -> str:
        return f"data: {json.dumps(asdict(self))}\n\n"


class SecurityEventBus:
    """Pub/sub event bus with a 500-event ring buffer and SSE fan-out."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._buffer: deque[SecurityEvent] = deque(maxlen=500)
        self._lock = asyncio.Lock()

        # Counters for dashboard stats
        self.counts: dict[str, int] = {
            "total": 0,
            "injection": 0,
            "blocked": 0,
            "tool_calls": 0,
        }

    def emit(self, event: SecurityEvent) -> None:
        """Sync, non-blocking. Safe to call from any context."""
        self._buffer.append(event)
        self._update_counts(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Slow subscriber — drop rather than block

    def _update_counts(self, event: SecurityEvent) -> None:
        self.counts["total"] += 1
        if event.type in ("INJECTION_PROBE", "INJECTION_BLOCKED"):
            self.counts["injection"] += 1
        if event.type in ("INJECTION_BLOCKED", "TOOL_BLOCKED"):
            self.counts["blocked"] += 1
        if event.type == "TOOL_CALL":
            self.counts["tool_calls"] += 1

    async def subscribe(self) -> AsyncGenerator[SecurityEvent, None]:
        """Yields all new events. On connect, replays last 50 buffered events."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        # Hydrate with recent history
        for event in list(self._buffer)[-50:]:
            await q.put(event)
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            self._subscribers.remove(q)


# Global singleton
bus = SecurityEventBus()
