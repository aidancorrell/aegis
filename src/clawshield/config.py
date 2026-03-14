"""ClawShield configuration — loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CLAWSHIELD_", "env_file": "clawshield.env", "extra": "ignore"}

    # Real API keys (held only by ClawShield, never passed to agent)
    real_openai_api_key: str = ""
    real_anthropic_api_key: str = ""
    real_gemini_api_key: str = ""

    # Security behavior
    block_injections: bool = False

    # Audit log path (shared volume from agent container)
    audit_log_path: str = "/mnt/agent-audit/audit.log"

    # Mode: "proxy" (wrap external agent) or "builtin" (engine.py)
    mode: str = "builtin"

    # Agent config file path (Mode B)
    agent_config_path: str = "/app/agent_config.json"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Workspace
    workspace_path: Path = Path("/app/workspace")


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
