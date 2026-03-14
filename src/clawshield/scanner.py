"""Injection detection and credential leak scanning.

Scans LLM message bodies (especially tool results) for prompt injection patterns
and credential leaks. No LLM call required — fast regex only.
"""

import re
from dataclasses import dataclass


# --- Injection patterns ---
# Focus on tool result messages (highest-risk ClawJacked vector)
_INJECTION_PATTERNS = [
    # Classic instruction hijacking
    re.compile(r"ignore\s+(previous|all|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(previous|all|prior|above)\s+instructions", re.I),
    re.compile(r"forget\s+(previous|all|prior)\s+instructions", re.I),
    # Role / persona injection
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bact\s+as\b.{0,40}\b(assistant|ai|bot|agent|gpt|claude|gemini)\b", re.I),
    re.compile(r"\bnew\s+(role|persona|identity|instruction)\b", re.I),
    re.compile(r"\bpretend\s+(you\s+are|to\s+be)\b", re.I),
    # Jailbreak keywords
    re.compile(r"\bDAN\s+mode\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bdo\s+anything\s+now\b", re.I),
    # Prompt structure injection
    re.compile(r"\bsystem:\s", re.I),
    re.compile(r"\bASSISTANT:\s"),
    re.compile(r"\bUSER:\s"),
    re.compile(r"\bHUMAN:\s"),
    # Token-style wrappers
    re.compile(r"\[\[.*?\]\]"),
    re.compile(r"<\|.*?\|>"),
    re.compile(r"<s>\s*\[INST\]"),
    # Exfiltration attempts targeting agent files
    re.compile(r"exfiltrate\s+.{0,60}(soul|identity|memory|key|token|secret)", re.I),
    re.compile(r"send\s+.{0,40}(soul\.md|identity\.md|memory\.md|\.env)", re.I),
]

# --- Credential leak patterns (in tool call args / responses) ---
_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),          # OpenAI API key (sk- and sk-proj-)
    re.compile(r"AKIA[A-Z0-9]{16}"),                 # AWS access key
    re.compile(r"AIza[A-Za-z0-9_\-]{35}"),           # Google API key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),              # GitHub personal access token
    re.compile(r"xoxb-[A-Za-z0-9\-]{40,}"),          # Slack bot token
    re.compile(r"eyJ[A-Za-z0-9_\-]{30,}\.eyJ"),      # JWT token
]


@dataclass
class ScanResult:
    has_injection: bool
    has_credential: bool
    matched_patterns: list[str]
    snippet: str  # Short excerpt for the dashboard card


def scan_text(text: str) -> ScanResult:
    """Scan a single text string for injection and credential patterns."""
    matched: list[str] = []
    snippet = text[:200] if len(text) > 200 else text

    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            matched.append(f"injection:{m.group(0)[:60]}")

    for pattern in _CREDENTIAL_PATTERNS:
        m = pattern.search(text)
        if m:
            matched.append(f"credential:{m.group(0)[:20]}...")

    has_injection = any(p.startswith("injection:") for p in matched)
    has_credential = any(p.startswith("credential:") for p in matched)
    return ScanResult(
        has_injection=has_injection,
        has_credential=has_credential,
        matched_patterns=matched,
        snippet=snippet,
    )


def scan_messages(messages: list[dict]) -> list[ScanResult]:
    """Scan an array of LLM request messages.

    Focuses on tool result content (role=tool / type=tool_result) as the
    primary ClawJacked injection vector. Also scans user messages.
    """
    results: list[ScanResult] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # OpenAI / Gemini: tool role with string content
        if role == "tool" and isinstance(content, str):
            results.append(scan_text(content))
            continue

        # Anthropic: user role with list content containing tool_result blocks
        if role == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    block_content = block.get("content", "")
                    if isinstance(block_content, str):
                        results.append(scan_text(block_content))
                    elif isinstance(block_content, list):
                        for sub in block_content:
                            if isinstance(sub, dict) and sub.get("type") == "text":
                                results.append(scan_text(sub.get("text", "")))
            continue

        # User messages (lower priority but still scan)
        if role == "user" and isinstance(content, str):
            results.append(scan_text(content))

    return [r for r in results if r.has_injection or r.has_credential]
