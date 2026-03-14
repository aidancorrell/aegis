"""Unit tests for clawshield.config."""

import pytest
from clawshield.config import Settings


class TestSettingsDefaults:
    def test_block_injections_default_true(self):
        s = Settings(_env_file=None)
        assert s.block_injections is True

    def test_port_default(self):
        s = Settings(_env_file=None)
        assert s.port == 8000

    def test_host_default(self):
        s = Settings(_env_file=None)
        assert s.host == "0.0.0.0"

    def test_api_keys_default_empty(self):
        s = Settings(_env_file=None)
        assert s.real_openai_api_key == ""
        assert s.real_anthropic_api_key == ""
        assert s.real_gemini_api_key == ""

    def test_audit_log_path_default(self):
        s = Settings(_env_file=None)
        assert s.audit_log_path == "/mnt/agent-audit/audit.log"


class TestSettingsEnvOverride:
    def test_block_injections_env_false(self, monkeypatch):
        monkeypatch.setenv("CLAWSHIELD_BLOCK_INJECTIONS", "false")
        s = Settings(_env_file=None)
        assert s.block_injections is False

    def test_port_env_override(self, monkeypatch):
        monkeypatch.setenv("CLAWSHIELD_PORT", "9090")
        s = Settings(_env_file=None)
        assert s.port == 9090

    def test_api_key_env_override(self, monkeypatch):
        monkeypatch.setenv("CLAWSHIELD_REAL_ANTHROPIC_API_KEY", "sk-ant-test123")
        s = Settings(_env_file=None)
        assert s.real_anthropic_api_key == "sk-ant-test123"
