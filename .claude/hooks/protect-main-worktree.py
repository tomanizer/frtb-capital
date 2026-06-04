#!/usr/bin/env python3
"""Block Claude file edits in the protected main checkout."""

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


def _tool_path(payload: dict[str, Any]) -> Path | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        return Path(cwd) / path
    return path


def _worktree_task_root(path: Path) -> Path | None:
    root = _real(APPROVED_CLAUDE_ROOT)
    target = _real(path)
    if not _is_relative_to(target, root):
        return None
    try:
        relative = target.relative_to(root)
    except ValueError:
        relative = Path(*target.parts[len(root.parts) :])
    if len(relative.parts) < 2:
        return None
    return root / relative.parts[0]


def _registered_claude_worktree(path: Path) -> bool:
    task_root = _worktree_task_root(path)
    if task_root is None or not task_root.exists():
        return False
    top_level = subprocess.run(
        ["git", "-C", str(task_root), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if top_level.returncode != 0:
        return False
    if _real(Path(top_level.stdout.strip())) != _real(task_root):
        return False
    branch = subprocess.run(
        ["git", "-C", str(task_root), "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
    )
    return branch.returncode == 0 and branch.stdout.strip().startswith("claude/")


def decision_for(payload: dict[str, Any]) -> tuple[bool, str]:
    """Return whether the tool call is allowed and the reason."""
    target = _tool_path(payload)
    if target is None:
        return True, ""

    if _is_relative_to(target, APPROVED_CLAUDE_ROOT):
        if _registered_claude_worktree(target):
            return True, ""
        return (
            False,
            "Claude may only edit registered worktrees under "
            f"{APPROVED_CLAUDE_ROOT}/<task> on a claude/<task> branch. "
            "Run `make agent-ensure AGENT=claude TASK=<task-name>` first.",
        )

    if _is_relative_to(target, PROTECTED_MAIN):
        return (
            False,
            "Blocked edit in protected main checkout. Do not write under "
            f"{PROTECTED_MAIN}. Run `make agent-ensure AGENT=claude "
            "TASK=<task-name>`, cd to the printed worktree under "
            f"{APPROVED_CLAUDE_ROOT}, and retry there.",
        )

    return True, ""


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
    allowed, reason = decision_for(payload)
    if allowed:
        return 0
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(output) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
