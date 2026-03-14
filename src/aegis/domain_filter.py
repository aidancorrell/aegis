"""Domain allow/block filtering for outbound web requests.

Two modes (controlled by AEGIS_DOMAIN_FILTER_MODE):

  blacklist  — allow all domains except those listed in domain_blacklist (default)
  whitelist  — block all domains except those listed in domain_whitelist

Domains are matched exactly or as a suffix (e.g. "openai.com" also matches
"api.openai.com"). Matching is case-insensitive.

Configure via aegis.env:
  AEGIS_DOMAIN_FILTER_MODE=whitelist
  AEGIS_DOMAIN_WHITELIST=api.openai.com,api.anthropic.com,generativelanguage.googleapis.com
  AEGIS_DOMAIN_BLACKLIST=evil.com,exfil.io
"""

from urllib.parse import urlparse

from .config import Settings
from .events import SecurityEvent, bus


def _parse_domains(raw: str) -> set[str]:
    """Split a comma-separated domain string into a lowercase set."""
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _matches(hostname: str, domains: set[str]) -> bool:
    """Return True if hostname equals any domain in the set or is a subdomain of one."""
    hostname = hostname.lower()
    return any(hostname == d or hostname.endswith("." + d) for d in domains)


def check_domain(url: str, settings: Settings) -> tuple[bool, str]:
    """Check whether *url* is permitted by the current domain filter.

    Returns (allowed, reason).  allowed=True means the request may proceed.
    Emits a DOMAIN_BLOCKED event when the request is denied.
    """
    hostname = (urlparse(url).hostname or "").lower()
    mode = settings.domain_filter_mode.lower()

    if mode == "whitelist":
        whitelist = _parse_domains(settings.domain_whitelist)
        if not whitelist:
            reason = f"domain '{hostname}' blocked — whitelist mode is active but whitelist is empty"
            _emit_blocked(url, hostname, reason)
            return False, reason
        if _matches(hostname, whitelist):
            return True, ""
        reason = f"domain '{hostname}' is not in the whitelist"
        _emit_blocked(url, hostname, reason)
        return False, reason

    else:  # blacklist mode (default)
        blacklist = _parse_domains(settings.domain_blacklist)
        if blacklist and _matches(hostname, blacklist):
            reason = f"domain '{hostname}' is on the blacklist"
            _emit_blocked(url, hostname, reason)
            return False, reason
        return True, ""


def _emit_blocked(url: str, hostname: str, reason: str) -> None:
    bus.emit(SecurityEvent(
        type="DOMAIN_BLOCKED",
        severity="high",
        data={"hostname": hostname, "url": url, "reason": reason},
    ))
