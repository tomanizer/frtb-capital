"""Tests for the repository-level agent worktree helper."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_agent_worktree() -> ModuleType:
    script_path = REPO_ROOT / "scripts" / "agent_worktree.py"
    spec = importlib.util.spec_from_file_location("agent_worktree", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_worktree"] = module
    spec.loader.exec_module(module)
    return module


def test_remote_branch_exists_checks_remote_heads(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_worktree = load_agent_worktree()
    git_calls: list[tuple[list[str], Path, bool]] = []

    def fake_git(
        args: list[str],
        cwd: Path,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        git_calls.append((args, cwd, check))
        return subprocess.CompletedProcess(args, 0, "", "")

    main_clone = Path("/repo")
    monkeypatch.setattr(agent_worktree, "git", fake_git)

    assert agent_worktree.remote_branch_exists(main_clone, "codex/task")
    assert git_calls == [
        (
            ["ls-remote", "--exit-code", "--heads", "origin", "codex/task"],
            main_clone,
            False,
        )
    ]


def test_create_worktree_tracks_existing_remote_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    main_clone.mkdir()
    worktree_root = tmp_path / "frtb-capital-worktrees"
    git_calls: list[list[str]] = []

    def fake_git(
        args: list[str],
        cwd: Path,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        git_calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    monkeypatch.setattr(agent_worktree, "local_branch_exists", lambda main, branch: False)
    monkeypatch.setattr(agent_worktree, "remote_branch_exists", lambda main, branch: True)
    monkeypatch.setattr(agent_worktree, "git", fake_git)

    args = Namespace(
        main_clone=main_clone,
        worktree_root=worktree_root,
        agent="codex",
        task="task",
        branch=None,
        path=None,
        no_sync=True,
    )

    assert agent_worktree.create_worktree(args) == 0
    assert git_calls == [
        [
            "worktree",
            "add",
            "--track",
            "-b",
            "codex/task",
            str((worktree_root / "codex" / "task").resolve()),
            "origin/codex/task",
        ]
    ]


def test_create_worktree_requires_exact_agent_task_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    main_clone.mkdir()
    worktree_root = tmp_path / "frtb-capital-worktrees"

    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    args = Namespace(
        main_clone=main_clone,
        worktree_root=worktree_root,
        agent="codex",
        task="task",
        branch=None,
        path=worktree_root / "codex",
        no_sync=True,
    )

    with pytest.raises(agent_worktree.AgentWorktreeError, match="exactly"):
        agent_worktree.create_worktree(args)

    args.path = worktree_root / "codex" / "task" / "extra"
    with pytest.raises(agent_worktree.AgentWorktreeError, match="exactly"):
        agent_worktree.create_worktree(args)


def test_guard_rejects_branch_without_agent_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    current = tmp_path / "frtb-capital-worktrees" / "codex" / "task"
    main_clone.mkdir()
    current.mkdir(parents=True)

    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    monkeypatch.setattr(agent_worktree, "resolve_repo_root", lambda path: current)
    monkeypatch.setattr(agent_worktree, "current_branch", lambda path: "task")

    args = Namespace(
        main_clone=main_clone,
        worktree_root=tmp_path / "frtb-capital-worktrees",
        quiet=False,
    )

    assert agent_worktree.guard(args) == 1
    assert "branch 'task' must be named <agent>/<task>" in capsys.readouterr().out


def test_guard_rejects_nested_worktree_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    current = tmp_path / "frtb-capital-worktrees" / "codex" / "task" / "extra"
    main_clone.mkdir()
    current.mkdir(parents=True)

    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    monkeypatch.setattr(agent_worktree, "resolve_repo_root", lambda path: current)
    monkeypatch.setattr(agent_worktree, "current_branch", lambda path: "codex/task")

    args = Namespace(
        main_clone=main_clone,
        worktree_root=tmp_path / "frtb-capital-worktrees",
        quiet=False,
    )

    assert agent_worktree.guard(args) == 1
    assert "worktree path must be <worktree-root>/<agent>/<task>" in capsys.readouterr().out


def test_doctor_accepts_absolute_hooks_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    main_clone.mkdir()
    hooks_dir = main_clone / ".githooks"
    hooks_dir.mkdir()

    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    monkeypatch.setattr(agent_worktree, "current_branch", lambda path: "main")
    monkeypatch.setattr(agent_worktree, "status_porcelain", lambda path: "")
    monkeypatch.setattr(agent_worktree, "git_optional_output", lambda args, cwd: str(hooks_dir))
    monkeypatch.setattr(
        agent_worktree,
        "parse_worktrees",
        lambda main: [agent_worktree.Worktree(main_clone, "refs/heads/main", False)],
    )

    args = Namespace(
        main_clone=main_clone,
        worktree_root=tmp_path / "frtb-capital-worktrees",
    )

    assert agent_worktree.doctor(args) == 0
