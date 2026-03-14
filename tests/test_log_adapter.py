"""Unit tests for clawshield.log_adapter._emit_from_entry."""

from unittest.mock import patch

from clawshield.events import SecurityEventBus
from clawshield.log_adapter import _emit_from_entry


def make_bus() -> SecurityEventBus:
    return SecurityEventBus()


class TestEmitFromEntry:
    def test_no_error_emits_tool_call(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "read_file", "result": "file contents"})
        assert len(bus._buffer) == 1
        event = bus._buffer[0]
        assert event.type == "TOOL_CALL"
        assert event.data["tool"] == "read_file"
        assert "result_snippet" in event.data

    def test_error_emits_tool_blocked(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "write_file", "error": "Permission denied"})
        event = bus._buffer[0]
        assert event.type == "TOOL_BLOCKED"
        assert event.severity == "high"

    def test_long_error_truncated_to_300(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "x", "error": "e" * 400})
        event = bus._buffer[0]
        assert len(event.data["error"]) == 300

    def test_long_result_truncated_to_200(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "x", "result": "r" * 300})
        event = bus._buffer[0]
        assert len(event.data["result_snippet"]) == 200

    def test_missing_tool_defaults_to_unknown(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"result": "ok"})
        event = bus._buffer[0]
        assert event.data["tool"] == "unknown"

    def test_timestamp_passed_through(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "x", "timestamp": "2024-01-01T00:00:00Z"})
        event = bus._buffer[0]
        assert event.timestamp == "2024-01-01T00:00:00Z"

    def test_missing_timestamp_auto_filled(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "x"})
        event = bus._buffer[0]
        assert event.timestamp  # non-empty string

    def test_error_data_includes_tool(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "dangerous_tool", "error": "blocked"})
        event = bus._buffer[0]
        assert event.data["tool"] == "dangerous_tool"
        assert event.data["source"] == "audit_log"

    def test_tool_call_source_is_audit_log(self):
        bus = make_bus()
        with patch("clawshield.log_adapter.bus", bus):
            _emit_from_entry({"tool": "read", "result": "data"})
        event = bus._buffer[0]
        assert event.data["source"] == "audit_log"
