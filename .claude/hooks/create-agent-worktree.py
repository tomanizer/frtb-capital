#!/usr/bin/env python3
"""Route Claude isolated worktrees through the repository worktree helper."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROTECTED_MAIN = Path(
    os.environ.get("FRTB_AGENT_MAIN_CLONE", "/Users/thomas/Projects/frtb-capital")
).expanduser()
WORKTREE_ROOT = Path(
    os.environ.get(
        "FRTB_AGENT_WORKTREE_ROOT",
        "/Users/thomas/Projects/frtb-capital-worktrees",
    )
).expanduser()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-._")
    return slug or "claude-session"


def _registered_worktree(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(PROTECTED_MAIN), "worktree", "list", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    needle = f"worktree {path.expanduser().resolve(strict=False)}"
    return needle in result.stdout.splitlines()


def _requested_task(payload: dict[str, Any]) -> str:
    for key in ("name", "task", "session_title", "agent_type"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return slugify(value)
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id.strip():
        return slugify(session_id[:12])
    return "claude-session"


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
    task = _requested_task(payload)
    target = WORKTREE_ROOT / "claude" / task

    if target.exists():
        if _registered_worktree(target):
            sys.stdout.write(str(target.expanduser().resolve(strict=False)) + "\n")
            return 0
        sys.stderr.write(f"refusing to use existing non-worktree path: {target}\n")
        return 1

    command = [
        sys.executable,
        "scripts/agent_worktree.py",
        "new",
        "--agent",
        "claude",
        "--no-sync",
        task,
    ]
    result = subprocess.run(
        command,
        cwd=PROTECTED_MAIN,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        sys.stderr.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode

    sys.stdout.write(str(target.expanduser().resolve(strict=False)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
