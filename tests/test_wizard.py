"""Unit tests for aegis.wizard."""

import pytest
import httpx
from httpx import ASGITransport
from fastapi import FastAPI

from aegis.wizard import (
    router as wizard_router,
    _default_extra_hosts,
    _generate_compose,
)

# Build a minimal app — avoids importing main.py (which calls load_settings())
wizard_app = FastAPI()
wizard_app.include_router(wizard_router)


class TestDefaultExtraHosts:
    def test_anthropic(self):
        assert _default_extra_hosts("anthropic") == ["api.anthropic.com"]

    def test_openai(self):
        assert _default_extra_hosts("openai") == ["api.openai.com"]

    def test_unknown_returns_empty(self):
        assert _default_extra_hosts("unknown") == []

    def test_gemini(self):
        assert _default_extra_hosts("gemini") == ["generativelanguage.googleapis.com"]


class TestGenerateCompose:
    def test_contains_agent_image(self):
        result = _generate_compose("my/image:latest", [])
        assert "my/image:latest" in result

    def test_contains_extra_hosts(self):
        result = _generate_compose("img:v1", ["api.openai.com", "api.anthropic.com"])
        assert "api.openai.com" in result
        assert "api.anthropic.com" in result

    def test_security_read_only(self):
        result = _generate_compose("img:v1", [])
        assert "read_only: true" in result

    def test_security_no_new_privileges(self):
        result = _generate_compose("img:v1", [])
        assert "no-new-privileges" in result

    def test_security_cap_drop(self):
        result = _generate_compose("img:v1", [])
        assert "cap_drop" in result

    def test_no_extra_hosts_empty_section(self):
        result = _generate_compose("img:v1", [])
        assert "extra_hosts:" in result


class TestWizardEndpoints:
    @pytest.mark.asyncio
    async def test_list_agents_returns_three(self):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.get("/wizard/agents")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_list_agents_fields(self):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.get("/wizard/agents")
        for agent in resp.json()["agents"]:
            assert "name" in agent
            assert "description" in agent
            assert "compatibility" in agent
            assert "image" in agent

    @pytest.mark.asyncio
    async def test_validate_key_anthropic_valid(self):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/wizard/validate-key?provider=anthropic&api_key=sk-ant-abcdefghijklmnopqrst"
            )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_key_anthropic_short_invalid(self):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/wizard/validate-key?provider=anthropic&api_key=short"
            )
        assert resp.json()["valid"] is False

    @pytest.mark.asyncio
    async def test_validate_key_openai_valid(self):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/wizard/validate-key?provider=openai&api_key=sk-abcdefghijklmnopqrst"
            )
        assert resp.json()["valid"] is True

    @pytest.mark.asyncio
    async def test_generate_mako_anthropic_real_key_in_aegis_env(self):
        payload = {
            "agent_name": "mako",
            "llm_provider": "anthropic",
            "llm_api_key": "sk-ant-realkey123456789",
        }
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post("/wizard/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "sk-ant-realkey123456789" in data["aegis_env"]

    @pytest.mark.asyncio
    async def test_generate_mako_anthropic_dummy_key_in_agent_env(self):
        payload = {
            "agent_name": "mako",
            "llm_provider": "anthropic",
            "llm_api_key": "sk-ant-realkey123456789",
        }
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post("/wizard/generate", json=payload)
        data = resp.json()
        assert "DUMMY_KEY_INTERCEPTED_BY_AEGIS" in data["agent_env"]

    @pytest.mark.asyncio
    async def test_generate_mako_anthropic_base_url_in_agent_env(self):
        payload = {
            "agent_name": "mako",
            "llm_provider": "anthropic",
            "llm_api_key": "sk-ant-realkey123456789",
        }
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post("/wizard/generate", json=payload)
        data = resp.json()
        assert "ANTHROPIC_BASE_URL" in data["agent_env"]

    @pytest.mark.asyncio
    async def test_generate_unknown_agent_uses_custom_image(self):
        payload = {
            "agent_name": "nonexistent",
            "custom_image": "my-custom/agent:v2",
            "llm_provider": "openai",
            "llm_api_key": "sk-real123456789012345",
        }
        async with httpx.AsyncClient(
            transport=ASGITransport(app=wizard_app), base_url="http://test"
        ) as client:
            resp = await client.post("/wizard/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "my-custom/agent:v2" in data["compose_content"]
