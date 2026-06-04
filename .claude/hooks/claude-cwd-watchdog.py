#!/usr/bin/env python3
"""Warn Claude when a session is running from the protected main checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROTECTED_MAIN = Path(
    os.environ.get("FRTB_AGENT_MAIN_CLONE", "/Users/thomas/Projects/frtb-capital")
)
APPROVED_CLAUDE_ROOT = Path(
    os.environ.get(
        "FRTB_AGENT_CLAUDE_WORKTREE_ROOT",
        "/Users/thomas/Projects/frtb-capital-worktrees/claude",
    )
)


def _real(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, parent: Path) -> bool:
    path_text = str(_real(path)).casefold()
    parent_text = str(_real(parent)).rstrip(os.sep).casefold()
    return path_text == parent_text or path_text.startswith(parent_text + os.sep)


def _branch(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def warning_for(payload: dict[str, Any]) -> str:
    """Return the startup warning, or an empty string when cwd is compliant."""
    raw_cwd = payload.get("new_cwd") or payload.get("cwd")
    if not isinstance(raw_cwd, str) or not raw_cwd:
        return ""
    cwd = _real(Path(raw_cwd))
    protected = _real(PROTECTED_MAIN)
    if not (_is_relative_to(cwd, protected) or _is_relative_to(cwd, APPROVED_CLAUDE_ROOT.parent)):
        return ""
    branch = _branch(cwd)
    if _is_relative_to(cwd, protected) or branch == "main":
        return (
            "FRTB workspace protection: this Claude session is in the protected "
            f"main checkout ({protected}) or on branch 'main'. Do not write files. "
            "Before edits, run `make agent-ensure AGENT=claude TASK=<task-name>` "
            f"and cd to the printed worktree under {APPROVED_CLAUDE_ROOT}."
        )
    return ""


def _load_payload() -> dict[str, Any] | None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        sys.stderr.write("Error: Invalid JSON payload on stdin\n")
        return None
    if not isinstance(payload, dict):
        sys.stderr.write("Error: Invalid JSON payload on stdin\n")
        return None
    return payload


def main() -> int:
    payload = _load_payload()
    if payload is None:
        return 1
    warning = warning_for(payload)
    if not warning:
        return 0
    event = payload.get("hook_event_name") or "SessionStart"
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": warning,
                },
                "systemMessage": warning,
            }
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
