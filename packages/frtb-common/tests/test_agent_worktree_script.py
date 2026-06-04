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


def test_policy_paths_discover_main_worktree_and_sibling_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    current = tmp_path / "frtb-capital-worktrees" / "codex" / "task"
    main_clone.mkdir()
    current.mkdir(parents=True)

    monkeypatch.setattr(agent_worktree, "resolve_repo_root", lambda path: current)
    monkeypatch.setattr(
        agent_worktree,
        "parse_worktrees",
        lambda path: [
            agent_worktree.Worktree(main_clone, "refs/heads/main", False),
            agent_worktree.Worktree(current, "refs/heads/codex/task", False),
        ],
    )
    monkeypatch.delenv(agent_worktree.ENV_MAIN_CLONE, raising=False)
    monkeypatch.delenv(agent_worktree.ENV_WORKTREE_ROOT, raising=False)
    monkeypatch.setattr(agent_worktree, "git_optional_output", lambda args, cwd: "")

    args = Namespace(main_clone=None, worktree_root=None)

    agent_worktree.resolve_policy_paths(args, cwd=current)

    assert args.main_clone == main_clone.resolve()
    assert args.worktree_root == (tmp_path / "frtb-capital-worktrees").resolve()


def test_policy_paths_prefer_environment_over_git_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_worktree = load_agent_worktree()
    env_main = tmp_path / "env-main"
    env_root = tmp_path / "env-worktrees"
    config_main = tmp_path / "config-main"
    config_root = tmp_path / "config-worktrees"

    monkeypatch.setenv(agent_worktree.ENV_MAIN_CLONE, str(env_main))
    monkeypatch.setenv(agent_worktree.ENV_WORKTREE_ROOT, str(env_root))

    def fake_git_optional_output(args: list[str], cwd: Path) -> str:
        key = args[-1]
        if key == agent_worktree.CONFIG_MAIN_CLONE:
            return str(config_main)
        if key == agent_worktree.CONFIG_WORKTREE_ROOT:
            return str(config_root)
        return ""

    monkeypatch.setattr(agent_worktree, "git_optional_output", fake_git_optional_output)

    args = Namespace(main_clone=None, worktree_root=None)

    agent_worktree.resolve_policy_paths(args, cwd=tmp_path)

    assert args.main_clone == env_main.resolve()
    assert args.worktree_root == env_root.resolve()


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


def test_ensure_passes_when_guard_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    current = tmp_path / "frtb-capital-worktrees" / "grok" / "task"
    main_clone.mkdir()
    current.mkdir(parents=True)

    monkeypatch.setattr(agent_worktree, "resolve_policy_paths", lambda args, cwd=None: None)
    monkeypatch.setattr(agent_worktree, "guard", lambda args: 0)
    monkeypatch.setattr(agent_worktree, "resolve_repo_root", lambda path: current)
    monkeypatch.setattr(agent_worktree, "current_branch", lambda path: "grok/task")

    args = Namespace(
        main_clone=main_clone,
        worktree_root=tmp_path / "frtb-capital-worktrees",
        agent="grok",
        task="task",
        quiet=False,
    )

    assert agent_worktree.ensure(args) == 0
    assert "already compliant" in capsys.readouterr().out


def test_ensure_reuses_existing_worktree_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    worktree_root = tmp_path / "frtb-capital-worktrees"
    worktree_path = worktree_root / "grok" / "task"
    main_clone.mkdir()
    worktree_path.mkdir(parents=True)

    monkeypatch.setattr(agent_worktree, "resolve_policy_paths", lambda args, cwd=None: None)
    monkeypatch.setattr(agent_worktree, "guard", lambda args: 1)
    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    monkeypatch.setattr(
        agent_worktree,
        "find_worktree_at_path",
        lambda main, path: agent_worktree.Worktree(worktree_path, "refs/heads/grok/task", False),
    )

    args = Namespace(
        main_clone=main_clone,
        worktree_root=worktree_root,
        agent="grok",
        task="task",
        quiet=False,
    )

    assert agent_worktree.ensure(args) == 0
    output = capsys.readouterr().out
    assert "reuse existing worktree" in output
    assert f"next: cd {worktree_path.resolve()}" in output


def test_ensure_creates_worktree_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_worktree = load_agent_worktree()
    main_clone = tmp_path / "frtb-capital"
    worktree_root = tmp_path / "frtb-capital-worktrees"
    main_clone.mkdir()
    created: list[Namespace] = []

    monkeypatch.setattr(agent_worktree, "resolve_policy_paths", lambda args, cwd=None: None)
    monkeypatch.setattr(agent_worktree, "guard", lambda args: 1)
    monkeypatch.setattr(agent_worktree, "require_main_clone", lambda path: main_clone)
    monkeypatch.setattr(agent_worktree, "find_worktree_at_path", lambda main, path: None)

    def fake_create(args: Namespace) -> int:
        created.append(args)
        return 0

    monkeypatch.setattr(agent_worktree, "create_worktree", fake_create)

    args = Namespace(
        main_clone=main_clone,
        worktree_root=worktree_root,
        agent="grok",
        task="new-task",
        branch=None,
        path=None,
        no_sync=False,
        quiet=True,
    )

    assert agent_worktree.ensure(args) == 0
    assert len(created) == 1
    assert created[0].agent == "grok"
    assert created[0].task == "new-task"
    assert created[0].branch == "grok/new-task"


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
