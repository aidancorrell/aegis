"""Unit tests for the SecurityEventBus."""

import asyncio
import pytest

from aegis.events import SecurityEvent, SecurityEventBus


def make_bus() -> SecurityEventBus:
    return SecurityEventBus()


class TestSecurityEvent:
    def test_default_timestamp_set(self):
        event = SecurityEvent(type="LLM_REQUEST", severity="info")
        assert event.timestamp  # non-empty string
        assert "T" in event.timestamp  # ISO-ish format

    def test_to_sse_format(self):
        event = SecurityEvent(type="LLM_REQUEST", severity="info", data={})
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")

    def test_data_defaults_to_empty_dict(self):
        event = SecurityEvent(type="LLM_REQUEST", severity="info")
        assert event.data == {}


class TestSecurityEventBus:
    def test_emit_updates_total_count(self):
        bus = make_bus()
        bus.emit(SecurityEvent(type="LLM_REQUEST", severity="info"))
        assert bus.counts["total"] == 1

    def test_emit_updates_injection_count(self):
        bus = make_bus()
        bus.emit(SecurityEvent(type="INJECTION_PROBE", severity="warn"))
        assert bus.counts["injection"] == 1

    def test_emit_injection_blocked_increments_both(self):
        bus = make_bus()
        bus.emit(SecurityEvent(type="INJECTION_BLOCKED", severity="critical"))
        assert bus.counts["injection"] == 1
        assert bus.counts["blocked"] == 1

    def test_emit_tool_blocked_increments_blocked(self):
        bus = make_bus()
        bus.emit(SecurityEvent(type="TOOL_BLOCKED", severity="high"))
        assert bus.counts["blocked"] == 1

    def test_emit_tool_call_increments_tool_calls(self):
        bus = make_bus()
        bus.emit(SecurityEvent(type="TOOL_CALL", severity="info"))
        assert bus.counts["tool_calls"] == 1

    def test_buffer_stores_events(self):
        bus = make_bus()
        bus.emit(SecurityEvent(type="LLM_REQUEST", severity="info"))
        assert len(bus._buffer) == 1

    def test_buffer_maxlen_500(self):
        bus = make_bus()
        for i in range(600):
            bus.emit(SecurityEvent(type="LLM_REQUEST", severity="info"))
        assert len(bus._buffer) == 500

    @pytest.mark.asyncio
    async def test_subscribe_receives_emitted_event(self):
        bus = make_bus()
        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event)
                break  # only take one

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0)  # let consumer subscribe
        bus.emit(SecurityEvent(type="LLM_REQUEST", severity="info"))
        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 1
        assert received[0].type == "LLM_REQUEST"

    @pytest.mark.asyncio
    async def test_subscribe_hydrates_last_50_buffered(self):
        bus = make_bus()
        for i in range(60):
            bus.emit(SecurityEvent(type="LLM_REQUEST", severity="info", data={"i": i}))

        received = []
        async def consumer():
            async for event in bus.subscribe():
                received.append(event)
                if len(received) >= 50:
                    break

        await asyncio.wait_for(asyncio.create_task(consumer()), timeout=2.0)
        assert len(received) == 50
        # Should be the last 50 (i=10..59)
        assert received[0].data["i"] == 10
        assert received[-1].data["i"] == 59
