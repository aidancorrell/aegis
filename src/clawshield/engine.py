"""ClawShield built-in ReAct agent engine.

Reads agent_config.json from the wizard. Supports Claude, Gemini, OpenAI.
All tool calls go through SecurityGuard and emit events to the bus natively.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .events import SecurityEvent, bus

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10


@dataclass
class AgentConfig:
    provider: str = "gemini"         # gemini | claude | openai
    api_key: str = ""
    model: str = ""
    system_prompt: str = "You are a helpful assistant."
    tools: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    workspace_path: str = "/app/workspace"


def load_agent_config(path: str) -> AgentConfig:
    p = Path(path)
    if not p.exists():
        return AgentConfig()
    try:
        data = json.loads(p.read_text())
        return AgentConfig(**{k: v for k, v in data.items() if k in AgentConfig.__dataclass_fields__})
    except Exception as e:
        logger.error("Failed to load agent config: %s", e)
        return AgentConfig()


# --- Minimal LLM clients ---

async def _call_gemini(api_key: str, model: str, messages: list[dict], tools: list[dict]) -> dict:
    model = model or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    system_parts = []
    contents = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
            continue
        if role == "tool":
            contents.append({"role": "function", "parts": [{"functionResponse": {"name": msg.get("name", "tool"), "response": {"result": content}}}]})
            continue
        parts = [{"text": content}] if content else []
        contents.append({"role": "user" if role == "user" else "model", "parts": parts})

    body: dict[str, Any] = {"contents": contents}
    if system_parts:
        body["system_instruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
    if tools:
        decls = [{"name": t["function"]["name"], "description": t["function"].get("description", ""), "parameters": t["function"].get("parameters", {})} for t in tools]
        body["tools"] = [{"function_declarations": decls}]

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=body, headers={"x-goog-api-key": api_key})
        resp.raise_for_status()
        return resp.json()


async def _call_anthropic(api_key: str, model: str, messages: list[dict], tools: list[dict]) -> dict:
    model = model or "claude-haiku-4-5-20251001"
    url = "https://api.anthropic.com/v1/messages"
    system_text = ""
    conversation = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        if role == "system":
            system_text += content + "\n"
            continue
        if role == "tool":
            conversation.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": msg.get("tool_call_id", ""), "content": content}]})
            continue
        if role == "assistant" and msg.get("tool_calls"):
            parts = []
            if content:
                parts.append({"type": "text", "text": content})
            for tc in msg["tool_calls"]:
                parts.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]})
            conversation.append({"role": "assistant", "content": parts})
            continue
        conversation.append({"role": role, "content": content})

    api_tools = [{"name": t["function"]["name"], "description": t["function"].get("description", ""), "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}})} for t in tools]

    body: dict[str, Any] = {"model": model, "max_tokens": 4096, "messages": conversation}
    if system_text.strip():
        body["system"] = system_text.strip()
    if api_tools:
        body["tools"] = api_tools

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=body, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        resp.raise_for_status()
        return resp.json()


async def _call_openai(api_key: str, model: str, messages: list[dict], tools: list[dict]) -> dict:
    model = model or "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"
    body: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=body, headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"})
        resp.raise_for_status()
        return resp.json()


# --- Tool implementations ---

_SSRF_PRIVATE = re.compile(
    r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|::1|localhost)",
    re.I,
)


async def _web_fetch(url: str, workspace_path: str) -> str:
    if not url.startswith("https://"):
        return "Error: only HTTPS URLs allowed"
    # Basic SSRF check
    import urllib.parse
    host = urllib.parse.urlparse(url).hostname or ""
    if _SSRF_PRIVATE.match(host):
        return "Error: private/local URLs not allowed"
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, max_redirects=5) as client:
            resp = await client.get(url, headers={"user-agent": "ClawShield/1.0"})
            resp.raise_for_status()
            text = resp.text
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:8000]
    except Exception as e:
        return f"Error fetching URL: {e}"


async def _read_file(path: str, workspace_path: str) -> str:
    try:
        wp = Path(workspace_path).resolve()
        target = (wp / path).resolve()
        target.relative_to(wp)  # jail check
        return target.read_text()[:10000]
    except ValueError:
        return "Error: path outside workspace"
    except Exception as e:
        return f"Error reading file: {e}"


async def _write_file(path: str, content: str, workspace_path: str) -> str:
    # Block protected files
    protected = {"soul.md", "identity.md", "memory.md"}
    if Path(path).name.lower() in protected:
        return "Error: cannot write to protected file"
    try:
        wp = Path(workspace_path).resolve()
        target = (wp / path).resolve()
        target.relative_to(wp)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"Written {len(content)} bytes to {path}"
    except ValueError:
        return "Error: path outside workspace"
    except Exception as e:
        return f"Error writing file: {e}"


async def _shell(command: str, allowed_commands: list[str]) -> str:
    import shlex
    from .scanner import _INJECTION_PATTERNS as _P
    METACHARACTERS = set("|;&`$(){}!\n\r\x00#><")
    for ch in METACHARACTERS:
        if ch in command:
            return f"Error: shell metacharacter '{ch}' not allowed"
    try:
        args = shlex.split(command)
    except ValueError as e:
        return f"Error: {e}"
    if not args:
        return "Error: empty command"
    base = Path(args[0]).name
    if base not in allowed_commands:
        return f"Error: command '{base}' not in allowlist {sorted(allowed_commands)}"
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode()[:8000]
    except asyncio.TimeoutError:
        return "Error: command timed out"
    except Exception as e:
        return f"Error: {e}"


# Tool registry
_TOOL_DEFINITIONS = {
    "web_fetch": {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch content from an HTTPS URL",
            "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "HTTPS URL to fetch"}}, "required": ["url"]},
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace",
            "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path within workspace"}}, "required": ["path"]},
        },
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        },
    },
    "shell": {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run an allowlisted shell command",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        },
    },
}


def _parse_tool_calls_from_response(data: dict, provider: str) -> tuple[str, list[dict]]:
    """Returns (text, tool_calls) from a raw provider response."""
    text = ""
    tool_calls = []

    if provider == "gemini":
        candidates = data.get("candidates", [])
        if not candidates:
            return "", []
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({"id": f"tc_{len(tool_calls)}", "name": fc["name"], "arguments": fc.get("args", {})})

    elif provider == "anthropic":
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({"id": block["id"], "name": block["name"], "arguments": block.get("input", {})})

    elif provider == "openai":
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        text = msg.get("content") or ""
        for tc in msg.get("tool_calls", []):
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            tool_calls.append({"id": tc["id"], "name": tc["function"]["name"], "arguments": args})

    return text, tool_calls


class BuiltinEngine:
    """Minimal ReAct loop powered by configured LLM provider."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._tools = [_TOOL_DEFINITIONS[t] for t in config.tools if t in _TOOL_DEFINITIONS]

    async def run(self, user_message: str, session_id: str = "default") -> str:
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": user_message},
        ]

        bus.emit(SecurityEvent(
            type="LLM_REQUEST",
            severity="info",
            data={"provider": self.config.provider, "message_count": len(messages), "tool_count": len(self._tools), "last_user_message": user_message[:200]},
        ))

        for iteration in range(MAX_ITERATIONS):
            start = time.monotonic()
            try:
                if self.config.provider == "gemini":
                    raw = await _call_gemini(self.config.api_key, self.config.model, messages, self._tools)
                elif self.config.provider == "anthropic":
                    raw = await _call_anthropic(self.config.api_key, self.config.model, messages, self._tools)
                else:
                    raw = await _call_openai(self.config.api_key, self.config.model, messages, self._tools)
            except Exception as e:
                logger.error("LLM call failed: %s", e)
                return f"Error: LLM call failed — {e}"

            latency_ms = int((time.monotonic() - start) * 1000)
            text, tool_calls = _parse_tool_calls_from_response(raw, self.config.provider)

            bus.emit(SecurityEvent(
                type="LLM_RESPONSE",
                severity="info",
                data={"provider": self.config.provider, "latency_ms": latency_ms, "has_tool_calls": bool(tool_calls)},
            ))

            if not tool_calls:
                return text or "(no response)"

            # Execute tool calls
            messages.append({"role": "assistant", "content": text, "tool_calls": tool_calls})

            for tc in tool_calls:
                name = tc["name"]
                args = tc["arguments"]

                # Security scan on tool arguments
                from .scanner import scan_text
                args_str = json.dumps(args)
                scan = scan_text(args_str)
                if scan.has_injection or scan.has_credential:
                    bus.emit(SecurityEvent(
                        type="INJECTION_PROBE",
                        severity="high",
                        data={"tool": name, "patterns": scan.matched_patterns, "snippet": scan.snippet},
                    ))

                bus.emit(SecurityEvent(
                    type="TOOL_CALL",
                    severity="info",
                    data={"tool": name, "args": {k: str(v)[:100] for k, v in args.items()}},
                ))

                try:
                    result = await self._execute_tool(name, args)
                except Exception as e:
                    result = f"Error: {e}"
                    bus.emit(SecurityEvent(
                        type="TOOL_BLOCKED",
                        severity="high",
                        data={"tool": name, "error": str(e)},
                    ))

                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result})

        return "Error: maximum iterations reached"

    async def _execute_tool(self, name: str, args: dict) -> str:
        wp = self.config.workspace_path
        if name == "web_fetch":
            return await _web_fetch(args.get("url", ""), wp)
        elif name == "read_file":
            return await _read_file(args.get("path", ""), wp)
        elif name == "write_file":
            return await _write_file(args.get("path", ""), args.get("content", ""), wp)
        elif name == "shell":
            return await _shell(args.get("command", ""), self.config.allowed_commands)
        return f"Unknown tool: {name}"
