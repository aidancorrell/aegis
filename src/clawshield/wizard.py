"""Setup wizard — generates clawshield.env + agent.env + docker-compose.yml for Mode A."""

import logging
from dataclasses import dataclass, field

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard")

# --- Agent registry ---

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


AGENT_REGISTRY: dict[str, AgentProfile] = {
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
}

_CLAWSHIELD_IP = "172.20.0.10"


# --- Request/response models ---

class ModeAConfig(BaseModel):
    agent_name: str = "mako"
    custom_image: str = ""
    llm_provider: str = "anthropic"
    llm_api_key: str
    telegram_bot_token: str = ""
    discord_bot_token: str = ""


class WizardResult(BaseModel):
    clawshield_env: str
    agent_env: str
    compose_content: str
    launch_command: str
    message: str


# --- Endpoints ---

@router.get("/agents")
async def list_agents() -> dict:
    return {
        "agents": [
            {
                "name": name,
                "description": p.description,
                "compatibility": p.compatibility,
                "image": p.image,
            }
            for name, p in AGENT_REGISTRY.items()
        ]
    }


@router.post("/generate", response_model=WizardResult)
async def generate(config: ModeAConfig) -> WizardResult:
    profile = AGENT_REGISTRY.get(config.agent_name)
    if profile is None:
        # Custom image
        profile = AgentProfile(
            image=config.custom_image or "ghcr.io/openclaw/openclaw:latest",
            llm_env_vars={config.llm_provider: config.llm_provider.upper() + "_API_KEY"},
            extra_hosts=_default_extra_hosts(config.llm_provider),
        )

    # clawshield.env
    cs_env_lines = [
        f"CLAWSHIELD_REAL_{config.llm_provider.upper()}_API_KEY={config.llm_api_key}",
        "CLAWSHIELD_BLOCK_INJECTIONS=true",
        "CLAWSHIELD_AUDIT_LOG_PATH=/mnt/agent-audit/audit.log",
    ]

    # agent.env (dummy keys — real keys stay in ClawShield)
    agent_env_lines = []
    for _provider, env_var in profile.llm_env_vars.items():
        agent_env_lines.append(f"{env_var}=DUMMY_KEY_INTERCEPTED_BY_CLAWSHIELD")

    # Route SDK calls through ClawShield proxy via env var (no DNS/TLS tricks needed)
    if config.llm_provider == "anthropic":
        agent_env_lines.append("ANTHROPIC_BASE_URL=http://clawshield:8000/proxy/anthropic")
    elif config.llm_provider == "openai":
        agent_env_lines.append("OPENAI_BASE_URL=http://clawshield:8000/proxy/openai")

    if config.telegram_bot_token:
        agent_env_lines.append(f"MAKO_TELEGRAM_BOT_TOKEN={config.telegram_bot_token}")
    if config.discord_bot_token:
        agent_env_lines.append(f"MAKO_DISCORD_BOT_TOKEN={config.discord_bot_token}")
    for k, v in profile.proxy_env.items():
        agent_env_lines.append(f"{k}={v}")

    compose = _generate_compose(profile.image, profile.extra_hosts)

    return WizardResult(
        clawshield_env="\n".join(cs_env_lines),
        agent_env="\n".join(agent_env_lines),
        compose_content=compose,
        launch_command="docker compose up -d",
        message=f"Generated two-container stack. Save clawshield.env and agent.env alongside docker-compose.yml, then run: docker compose up -d",
    )


@router.post("/validate-key")
async def validate_key(provider: str, api_key: str) -> dict:
    validators = {
        "openai": lambda k: k.startswith("sk-") and len(k) > 20,
        "anthropic": lambda k: k.startswith("sk-ant-") and len(k) > 20,
        "gemini": lambda k: len(k) > 10,
    }
    validator = validators.get(provider, lambda k: len(k) > 5)
    valid = validator(api_key)
    return {"valid": valid, "message": "Key format looks good" if valid else "Key format looks incorrect"}


# --- Compose generator ---

def _generate_compose(agent_image: str, extra_hosts: list[str]) -> str:
    hosts_yaml = "\n".join(f'      - "{h}:{_CLAWSHIELD_IP}"' for h in extra_hosts)
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
      - seccomp=seccomp.json
    cap_drop:
      - ALL
    mem_limit: 256m
    networks:
      clawnet:
        ipv4_address: {_CLAWSHIELD_IP}

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
    networks:
      - clawnet
    depends_on:
      - clawshield

networks:
  clawnet:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  agent-audit:
  agent-workspace:
"""


def _default_extra_hosts(provider: str) -> list[str]:
    mapping = {
        "gemini": ["generativelanguage.googleapis.com"],
        "anthropic": ["api.anthropic.com"],
        "openai": ["api.openai.com"],
    }
    return mapping.get(provider, [])
