"""Aegis configuration — loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "AEGIS_", "env_file": "aegis.env", "extra": "ignore"}

    # Real API keys (held only by Aegis, never passed to agent)
    real_openai_api_key: str = ""
    real_anthropic_api_key: str = ""
    real_gemini_api_key: str = ""

    # Security behavior
    block_injections: bool = True

    # Domain filter
    domain_filter_mode: str = "blacklist"  # "blacklist" or "whitelist"
    domain_whitelist: str = ""  # comma-separated domains
    domain_blacklist: str = ""  # comma-separated domains

    # Audit log path (shared volume from Mako container)
    audit_log_path: str = "/mnt/agent-audit/audit.log"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
