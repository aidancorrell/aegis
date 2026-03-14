"""Setup wizard — generates clawshield.env + agent_config.json + docker-compose.yml."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard")

# --- Agent registry for Mode A ---

@dataclass
class AgentProfile:
    image: str
    llm_env_vars: dict = field(default_factory=dict)
    audit_log_path: str = "/app/audit/audit.log"
    audit_format: str = "mako_jsonl"
    extra_hosts: list[str] = field(default_factory=list)
    proxy_env: dict = field(default_factory=dict)
    description: str = ""
    compatibility: str = "✓ Compatible"


AGENT_REGISTRY: dict[str, AgentProfile | None] = {
    "mako": AgentProfile(
        image="ghcr.io/aidancorrell/mako:latest",
        llm_env_vars={
            "gemini": "MAKO_GEMINI_API_KEY",
            "anthropic": "MAKO_ANTHROPIC_API_KEY",
        },
        audit_log_path="/app/audit/audit.log",
        audit_format="mako_jsonl",
        extra_hosts=["generativelanguage.googleapis.com", "api.anthropic.com", "api.openai.com"],
        description="The original OpenClaw-compatible agent",
        compatibility="✓ Full (proxy + audit log)",
    ),
    "zeroclaw": AgentProfile(
        image="ghcr.io/zeroclaw/zeroclaw:latest",
        llm_env_vars={"openai": "OPENAI_API_KEY"},
        proxy_env={"OPENAI_BASE_URL": "http://clawshield:8000/proxy/openai"},
        description="Security-focused OpenClaw fork",
        compatibility="✓ Proxy intercept",
    ),
    "openclaw": AgentProfile(
        image="ghcr.io/openclaw/openclaw:latest",
        llm_env_vars={"openai": "OPENAI_API_KEY"},
        extra_hosts=["api.openai.com"],
        description="Original OpenClaw",
        compatibility="✓ DNS proxy intercept",
    ),
    "builtin": None,  # Signals wizard to use engine.py, skip agent container
}

_PROVIDER_DEFAULTS = {
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}


# --- Request models ---

class ModeAConfig(BaseModel):
    agent_name: str = "mako"
    custom_image: str = ""
    llm_provider: str = "gemini"
    llm_api_key: str
    telegram_bot_token: str = ""
    discord_bot_token: str = ""
    deploy_target: str = "local"
    vps_host: str = ""
    vps_user: str = "ubuntu"


class ModeBConfig(BaseModel):
    llm_provider: str = "gemini"
    llm_api_key: str
    llm_model: str = ""
    system_prompt: str = "You are a helpful assistant."
    tools: list[str] = field(default_factory=lambda: ["web_fetch"])
    allowed_commands: list[str] = field(default_factory=list)
    telegram_bot_token: str = ""
    discord_bot_token: str = ""
    deploy_target: str = "local"
    vps_host: str = ""
    vps_user: str = "ubuntu"


class WizardResult(BaseModel):
    env_content: str
    compose_content: str
    agent_config: dict | None = None
    launch_command: str
    message: str


# --- Endpoints ---

@router.get("/agents")
async def list_agents() -> dict:
    agents = []
    for name, profile in AGENT_REGISTRY.items():
        if profile is None:
            agents.append({"name": name, "description": "Build your own agent (built-in engine)", "compatibility": "✓ Native", "image": None})
        else:
            agents.append({"name": name, "description": profile.description, "compatibility": profile.compatibility, "image": profile.image})
    return {"agents": agents}


@router.post("/generate/mode-a", response_model=WizardResult)
async def generate_mode_a(config: ModeAConfig) -> WizardResult:
    profile = AGENT_REGISTRY.get(config.agent_name)
    if profile is None and config.agent_name != "custom":
        profile = AgentProfile(
            image=config.custom_image or "ghcr.io/openclaw/openclaw:latest",
            llm_env_vars={config.llm_provider: config.llm_provider.upper() + "_API_KEY"},
            extra_hosts=_default_extra_hosts(config.llm_provider),
        )

    agent_image = profile.image if profile else config.custom_image

    # Generate clawshield.env
    env_lines = [
        f"CLAWSHIELD_REAL_{config.llm_provider.upper()}_API_KEY={config.llm_api_key}",
        "CLAWSHIELD_MODE=proxy",
        "CLAWSHIELD_BLOCK_INJECTIONS=false",
    ]
    if profile and profile.audit_log_path:
        env_lines.append(f"CLAWSHIELD_AUDIT_LOG_PATH=/mnt/agent-audit/audit.log")

    # Generate agent.env (dummy key)
    agent_env_lines = []
    if profile:
        for _provider, env_var in profile.llm_env_vars.items():
            agent_env_lines.append(f"{env_var}=DUMMY_KEY_INTERCEPTED_BY_CLAWSHIELD")
    if config.telegram_bot_token:
        agent_env_lines.append(f"MAKO_TELEGRAM_BOT_TOKEN={config.telegram_bot_token}")
    if config.discord_bot_token:
        agent_env_lines.append(f"MAKO_DISCORD_BOT_TOKEN={config.discord_bot_token}")
    if profile and profile.proxy_env:
        for k, v in profile.proxy_env.items():
            agent_env_lines.append(f"{k}={v}")

    # Generate docker-compose.yml
    extra_hosts = profile.extra_hosts if profile else _default_extra_hosts(config.llm_provider)
    compose = _generate_mode_a_compose(agent_image or "", extra_hosts)

    env_content = "\n".join(env_lines)
    # Write agent.env section as comment block
    agent_env_content = "\n".join(agent_env_lines)

    return WizardResult(
        env_content=env_content,
        compose_content=compose,
        agent_config=None,
        launch_command="docker compose up -d",
        message=f"Generated two-container stack with {config.agent_name} agent. Agent env:\n\n{agent_env_content}\n\nSave as agent.env",
    )


@router.post("/generate/mode-b", response_model=WizardResult)
async def generate_mode_b(config: ModeBConfig) -> WizardResult:
    model = config.llm_model or _PROVIDER_DEFAULTS.get(config.llm_provider, "")

    agent_config = {
        "provider": config.llm_provider,
        "api_key": config.llm_api_key,
        "model": model,
        "system_prompt": config.system_prompt,
        "tools": config.tools,
        "allowed_commands": config.allowed_commands,
        "workspace_path": "/app/workspace",
    }

    env_lines = [
        f"CLAWSHIELD_REAL_{config.llm_provider.upper()}_API_KEY={config.llm_api_key}",
        "CLAWSHIELD_MODE=builtin",
        "CLAWSHIELD_BLOCK_INJECTIONS=false",
    ]
    if config.telegram_bot_token:
        env_lines.append(f"CLAWSHIELD_TELEGRAM_BOT_TOKEN={config.telegram_bot_token}")

    compose = _generate_mode_b_compose()

    return WizardResult(
        env_content="\n".join(env_lines),
        compose_content=compose,
        agent_config=agent_config,
        launch_command="docker compose up -d",
        message="Generated single-container stack with built-in agent. Save agent_config.json alongside docker-compose.yml.",
    )


@router.post("/validate-key")
async def validate_key(provider: str, api_key: str) -> dict:
    """Quick format validation for API keys (no network call)."""
    import re
    validators = {
        "openai": lambda k: k.startswith("sk-") and len(k) > 20,
        "anthropic": lambda k: k.startswith("sk-ant-") and len(k) > 20,
        "gemini": lambda k: len(k) > 10,
    }
    validator = validators.get(provider, lambda k: len(k) > 5)
    valid = validator(api_key)
    return {"valid": valid, "message": "Key format looks good" if valid else "Key format looks incorrect"}


# --- Compose generators ---

def _generate_mode_a_compose(agent_image: str, extra_hosts: list[str]) -> str:
    hosts_yaml = "\n".join(f'      - "{h}:${{CLAWSHIELD_IP:-host-gateway}}"' for h in extra_hosts)
    return f"""services:
  clawshield:
    image: ghcr.io/clawshield/clawshield:latest
    ports:
      - "8000:8000"
    env_file: clawshield.env
    volumes:
      - agent-audit:/mnt/agent-audit:ro
      - agent-workspace:/mnt/agent-workspace:ro
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=32M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    mem_limit: 256m

  agent:
    image: {agent_image}
    env_file: agent.env
    extra_hosts:
{hosts_yaml}
    volumes:
      - agent-audit:/app/audit
      - agent-workspace:/app/workspace
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=64M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    mem_limit: 256m

volumes:
  agent-audit:
  agent-workspace:
"""


def _generate_mode_b_compose() -> str:
    return """services:
  clawshield:
    image: ghcr.io/clawshield/clawshield:latest
    ports:
      - "8000:8000"
    env_file: clawshield.env
    volumes:
      - ./agent_config.json:/app/agent_config.json:ro
      - agent-workspace:/app/workspace
      - agent-audit:/app/audit
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=32M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    mem_limit: 256m

volumes:
  agent-workspace:
  agent-audit:
"""


def _default_extra_hosts(provider: str) -> list[str]:
    mapping = {
        "gemini": ["generativelanguage.googleapis.com"],
        "anthropic": ["api.anthropic.com"],
        "openai": ["api.openai.com"],
    }
    return mapping.get(provider, [])
