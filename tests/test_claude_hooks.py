"""Tests for Claude workspace-protection hooks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_hook(name: str) -> ModuleType:
    module_name = name.replace("-", "_")
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = REPO_ROOT / ".claude" / "hooks" / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_protect_main_blocks_protected_checkout_edit() -> None:
    hook = load_hook("protect-main-worktree.py")

    allowed, reason = hook.decision_for(
        {
            "cwd": "/Users/thomas/Projects/frtb-capital",
            "tool_input": {"file_path": "docs/example.md"},
        }
    )

    assert allowed is False
    assert "protected main checkout" in reason
    assert "make agent-ensure AGENT=claude" in reason


def test_protect_main_accepts_registered_claude_worktree(monkeypatch) -> None:
    hook = load_hook("protect-main-worktree.py")
    monkeypatch.setattr(hook, "_registered_claude_worktree", lambda path: True)

    allowed, reason = hook.decision_for(
        {
            "tool_input": {
                "file_path": "/Users/thomas/Projects/frtb-capital-worktrees/claude/task/README.md"
            }
        }
    )

    assert allowed is True
    assert reason == ""


def test_protect_main_blocks_unregistered_claude_worktree(monkeypatch) -> None:
    hook = load_hook("protect-main-worktree.py")
    monkeypatch.setattr(hook, "_registered_claude_worktree", lambda path: False)

    allowed, reason = hook.decision_for(
        {
            "tool_input": {
                "file_path": "/Users/thomas/Projects/frtb-capital-worktrees/claude/task/README.md"
            }
        }
    )

    assert allowed is False
    assert "registered worktrees" in reason


def test_cwd_watchdog_warns_for_main_branch(monkeypatch) -> None:
    hook = load_hook("claude-cwd-watchdog.py")
    monkeypatch.setattr(hook, "_branch", lambda cwd: "main")

    warning = hook.warning_for({"cwd": "/Users/thomas/Projects/frtb-capital"})

    assert "protected main checkout" in warning
    assert "make agent-ensure AGENT=claude" in warning


def test_cwd_watchdog_is_quiet_for_claude_branch(monkeypatch) -> None:
    hook = load_hook("claude-cwd-watchdog.py")
    monkeypatch.setattr(hook, "_branch", lambda cwd: "claude/task")

    warning = hook.warning_for({"cwd": "/Users/thomas/Projects/frtb-capital-worktrees/claude/task"})

    assert warning == ""


def test_cwd_watchdog_ignores_unrelated_main_branch(monkeypatch) -> None:
    hook = load_hook("claude-cwd-watchdog.py")
    monkeypatch.setattr(hook, "_branch", lambda cwd: "main")

    warning = hook.warning_for({"cwd": "/Users/thomas/Projects/other-repo"})

    assert warning == ""
