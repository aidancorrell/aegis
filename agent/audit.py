"""Audit log writer — writes tool call entries in Mako's JSON-lines format.

Format understood by ClawShield's log_adapter.py:
  {"timestamp": "...", "tool": "...", "args": {...}, "result": "...", "error": "..."}
"""

import json
import time
from pathlib import Path

_LOG_PATH = Path("/app/audit/audit.log")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_tool_call(tool: str, args: dict, result: str) -> None:
    _write({"timestamp": _now(), "tool": tool, "args": args, "result": result[:500]})


def log_tool_blocked(tool: str, args: dict, error: str) -> None:
    _write({"timestamp": _now(), "tool": tool, "args": args, "error": error})


def _write(entry: dict) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # never crash the agent over logging
