"""Unit tests for aegis.hardening."""

from unittest.mock import patch

import pytest

from aegis.events import SecurityEventBus
from aegis.hardening import HardeningStatus, _emit, apply


class TestHardeningStatusDefaults:
    def test_landlock_active_false(self):
        s = HardeningStatus()
        assert s.landlock_active is False

    def test_seatbelt_active_false(self):
        s = HardeningStatus()
        assert s.seatbelt_active is False

    def test_no_new_privs_false(self):
        s = HardeningStatus()
        assert s.no_new_privs is False

    def test_landlock_reason_empty(self):
        s = HardeningStatus()
        assert s.landlock_reason == ""

    def test_seatbelt_reason_empty(self):
        s = HardeningStatus()
        assert s.seatbelt_reason == ""

    def test_platform_empty(self):
        s = HardeningStatus()
        assert s.platform == ""


class TestApplyWindowsBranch:
    def test_returns_hardening_status(self):
        test_bus = SecurityEventBus()
        with (
            patch("aegis.hardening._IS_LINUX", False),
            patch("aegis.hardening._IS_MACOS", False),
            patch("aegis.hardening.bus", test_bus),
        ):
            status = apply("/tmp/workspace", "/tmp/audit")
        assert isinstance(status, HardeningStatus)

    def test_landlock_inactive(self):
        test_bus = SecurityEventBus()
        with (
            patch("aegis.hardening._IS_LINUX", False),
            patch("aegis.hardening._IS_MACOS", False),
            patch("aegis.hardening.bus", test_bus),
        ):
            status = apply("/tmp/workspace", "/tmp/audit")
        assert status.landlock_active is False

    def test_seatbelt_inactive(self):
        test_bus = SecurityEventBus()
        with (
            patch("aegis.hardening._IS_LINUX", False),
            patch("aegis.hardening._IS_MACOS", False),
            patch("aegis.hardening.bus", test_bus),
        ):
            status = apply("/tmp/workspace", "/tmp/audit")
        assert status.seatbelt_active is False

    def test_landlock_reason_contains_unavailable_on(self):
        test_bus = SecurityEventBus()
        with (
            patch("aegis.hardening._IS_LINUX", False),
            patch("aegis.hardening._IS_MACOS", False),
            patch("aegis.hardening.bus", test_bus),
        ):
            status = apply("/tmp/workspace", "/tmp/audit")
        assert "unavailable on" in status.landlock_reason

    def test_emits_event(self):
        test_bus = SecurityEventBus()
        with (
            patch("aegis.hardening._IS_LINUX", False),
            patch("aegis.hardening._IS_MACOS", False),
            patch("aegis.hardening.bus", test_bus),
        ):
            apply("/tmp/workspace", "/tmp/audit")
        assert len(test_bus._buffer) == 1


class TestEmit:
    def test_both_inactive_emits_warn(self):
        test_bus = SecurityEventBus()
        status = HardeningStatus(platform="Linux")
        with patch("aegis.hardening.bus", test_bus):
            _emit(status)
        event = test_bus._buffer[0]
        assert event.severity == "warn"

    def test_both_inactive_landlock_field_contains_inactive(self):
        test_bus = SecurityEventBus()
        status = HardeningStatus(platform="Linux")
        with patch("aegis.hardening.bus", test_bus):
            _emit(status)
        event = test_bus._buffer[0]
        assert "inactive" in event.data["landlock"]

    def test_both_inactive_seatbelt_field_contains_inactive(self):
        test_bus = SecurityEventBus()
        status = HardeningStatus(platform="Linux")
        with patch("aegis.hardening.bus", test_bus):
            _emit(status)
        event = test_bus._buffer[0]
        assert "inactive" in event.data["seatbelt"]

    def test_landlock_active_emits_info(self):
        test_bus = SecurityEventBus()
        status = HardeningStatus(landlock_active=True, platform="Linux")
        with patch("aegis.hardening.bus", test_bus):
            _emit(status)
        event = test_bus._buffer[0]
        assert event.severity == "info"

    def test_seatbelt_active_emits_info(self):
        test_bus = SecurityEventBus()
        status = HardeningStatus(seatbelt_active=True, platform="Darwin")
        with patch("aegis.hardening.bus", test_bus):
            _emit(status)
        event = test_bus._buffer[0]
        assert event.severity == "info"

    def test_emit_event_type_is_tool_call(self):
        test_bus = SecurityEventBus()
        status = HardeningStatus()
        with patch("aegis.hardening.bus", test_bus):
            _emit(status)
        event = test_bus._buffer[0]
        assert event.type == "TOOL_CALL"
        assert event.data["tool"] == "hardening"
