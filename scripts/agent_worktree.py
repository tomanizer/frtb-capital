#!/usr/bin/env python3
"""Manage protected-main and agent-worktree workflow for frtb-capital."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_NAME = "frtb-capital"
MAIN_BRANCH = "main"
REMOTE = "origin"
CONFIG_MAIN_CLONE = "frtb.agentMainClone"
CONFIG_WORKTREE_ROOT = "frtb.agentWorktreeRoot"
ENV_MAIN_CLONE = "FRTB_AGENT_MAIN_CLONE"
ENV_WORKTREE_ROOT = "FRTB_AGENT_WORKTREE_ROOT"


class AgentWorktreeError(RuntimeError):
    """Raised when the requested worktree operation violates repository policy."""


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch_ref: str | None
    detached: bool

    @property
    def branch(self) -> str:
        if self.branch_ref is None:
            return "detached" if self.detached else "unknown"
        prefix = "refs/heads/"
        if self.branch_ref.startswith(prefix):
            return self.branch_ref.removeprefix(prefix)
        return self.branch_ref


def git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        command = "git " + " ".join(args)
        stderr = result.stderr.strip()
        raise AgentWorktreeError(f"{command} failed in {cwd}: {stderr}")
    return result


def git_output(args: list[str], cwd: Path) -> str:
    return git(args, cwd).stdout.strip()


def git_optional_output(args: list[str], cwd: Path) -> str:
    result = git(args, cwd, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def path_from_env(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def path_from_git_config(key: str, cwd: Path) -> Path | None:
    value = git_optional_output(["config", "--get", key], cwd)
    if not value:
        return None
    return Path(value).expanduser()


def resolve_repo_root(path: Path) -> Path:
    try:
        return Path(git_output(["rev-parse", "--show-toplevel"], path)).resolve()
    except AgentWorktreeError as exc:
        raise AgentWorktreeError(f"{path} is not inside a Git working tree") from exc


def require_main_clone(path: Path) -> Path:
    expanded = path.expanduser().resolve()
    if not expanded.exists():
        raise AgentWorktreeError(f"protected main clone does not exist: {expanded}")
    root = resolve_repo_root(expanded)
    if root != expanded:
        raise AgentWorktreeError(f"protected main clone must be a repo root: {expanded}")
    return root


def discover_main_clone(cwd: Path) -> Path:
    current = resolve_repo_root(cwd)
    main_worktrees = [
        worktree.path
        for worktree in parse_worktrees(current)
        if worktree.branch == MAIN_BRANCH and not worktree.detached
    ]
    if len(main_worktrees) == 1:
        return main_worktrees[0]
    if len(main_worktrees) > 1:
        raise AgentWorktreeError(
            f"multiple main worktrees found; set {CONFIG_MAIN_CLONE} or {ENV_MAIN_CLONE} explicitly"
        )
    if current_branch(current) == MAIN_BRANCH:
        return current
    raise AgentWorktreeError(
        f"could not discover protected main clone; set {CONFIG_MAIN_CLONE} or {ENV_MAIN_CLONE}"
    )


def default_worktree_root(main_clone: Path) -> Path:
    return main_clone.parent / f"{main_clone.name}-worktrees"


def resolve_policy_paths(args: argparse.Namespace, *, cwd: Path | None = None) -> None:
    lookup_cwd = cwd or Path.cwd()
    main_clone = (
        args.main_clone
        or path_from_env(ENV_MAIN_CLONE)
        or path_from_git_config(CONFIG_MAIN_CLONE, lookup_cwd)
        or discover_main_clone(lookup_cwd)
    )
    worktree_root = (
        args.worktree_root
        or path_from_env(ENV_WORKTREE_ROOT)
        or path_from_git_config(CONFIG_WORKTREE_ROOT, lookup_cwd)
        or default_worktree_root(main_clone)
    )
    args.main_clone = main_clone.expanduser().resolve()
    args.worktree_root = worktree_root.expanduser().resolve()


def current_branch(path: Path) -> str:
    return git_output(["branch", "--show-current"], path)


def status_porcelain(path: Path, *, include_untracked: bool = True) -> str:
    args = ["status", "--porcelain=v1"]
    if not include_untracked:
        args.append("--untracked-files=no")
    return git_output(args, path)


def local_branch_exists(main_clone: Path, branch: str) -> bool:
    result = git(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        main_clone,
        check=False,
    )
    return result.returncode == 0


def remote_branch_exists(main_clone: Path, branch: str) -> bool:
    result = git(
        ["ls-remote", "--exit-code", "--heads", REMOTE, branch],
        main_clone,
        check=False,
    )
    return result.returncode == 0


def parse_worktrees(main_clone: Path) -> list[Worktree]:
    output = git_output(["worktree", "list", "--porcelain"], main_clone)
    records = [record for record in output.split("\n\n") if record.strip()]
    worktrees: list[Worktree] = []
    for record in records:
        path: Path | None = None
        branch_ref: str | None = None
        detached = False
        for line in record.splitlines():
            if line.startswith("worktree "):
                path = Path(line.removeprefix("worktree ")).resolve()
            elif line.startswith("branch "):
                branch_ref = line.removeprefix("branch ")
            elif line == "detached":
                detached = True
        if path is None:
            raise AgentWorktreeError(f"could not parse worktree record: {record}")
        worktrees.append(Worktree(path=path, branch_ref=branch_ref, detached=detached))
    return worktrees


def slugify(value: str, *, label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    slug = slug.strip("-._")
    if not slug:
        raise AgentWorktreeError(f"{label} must contain at least one alphanumeric character")
    return slug


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def print_error(error: Exception) -> int:
    print(f"error: {error}", file=sys.stderr)
    return 1


def sync_main(args: argparse.Namespace) -> int:
    main_clone = require_main_clone(args.main_clone)
    branch = current_branch(main_clone)
    if branch != MAIN_BRANCH:
        raise AgentWorktreeError(
            f"protected main clone must stay on {MAIN_BRANCH!r}; current branch is {branch!r}"
        )

    dirty = status_porcelain(main_clone)
    if dirty:
        raise AgentWorktreeError(
            "protected main clone has local changes or untracked files; "
            "clean or move them before syncing"
        )

    git(["fetch", REMOTE, MAIN_BRANCH], main_clone)
    ahead_behind = git_output(
        ["rev-list", "--left-right", "--count", f"HEAD...{REMOTE}/{MAIN_BRANCH}"],
        main_clone,
    )
    ahead_text, behind_text = ahead_behind.split()
    ahead = int(ahead_text)
    behind = int(behind_text)
    if ahead:
        raise AgentWorktreeError(
            f"protected main clone is {ahead} commit(s) ahead of {REMOTE}/{MAIN_BRANCH}; "
            "do not keep local commits on main"
        )
    if behind:
        git(["merge", "--ff-only", f"{REMOTE}/{MAIN_BRANCH}"], main_clone)

    head = git_output(["rev-parse", "--short", "HEAD"], main_clone)
    print(f"{main_clone} is synced to {REMOTE}/{MAIN_BRANCH} at {head}")
    return 0


def create_worktree(args: argparse.Namespace) -> int:
    main_clone = require_main_clone(args.main_clone)
    worktree_root = args.worktree_root.expanduser().resolve()
    agent = slugify(args.agent, label="agent")

    task_source = args.task or args.branch or ""
    task = slugify(task_source.split("/", 1)[-1], label="task")
    branch = args.branch or f"{agent}/{task}"
    if "/" not in branch:
        raise AgentWorktreeError("agent worktree branches must be named <agent>/<task>")
    branch_agent = branch.split("/", 1)[0]
    if branch_agent != agent:
        raise AgentWorktreeError(
            f"branch {branch!r} must start with the selected agent prefix {agent!r}"
        )

    worktree_path = (args.path or worktree_root / agent / task).expanduser().resolve()
    if is_relative_to(worktree_path, main_clone):
        raise AgentWorktreeError(
            "agent worktrees must not be created inside the protected main clone"
        )
    if not is_relative_to(worktree_path, worktree_root):
        raise AgentWorktreeError(f"worktree path must be under {worktree_root}")
    relative_worktree = worktree_path.relative_to(worktree_root)
    if len(relative_worktree.parts) != 2 or relative_worktree.parts[0] != agent:
        raise AgentWorktreeError(f"worktree path must be exactly {worktree_root}/<agent>/<task>")
    if worktree_path.exists():
        raise AgentWorktreeError(f"worktree path already exists: {worktree_path}")

    if not args.no_sync:
        sync_main(args)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if local_branch_exists(main_clone, branch):
        git(["worktree", "add", str(worktree_path), branch], main_clone)
    elif remote_branch_exists(main_clone, branch):
        git(
            ["worktree", "add", "--track", "-b", branch, str(worktree_path), f"{REMOTE}/{branch}"],
            main_clone,
        )
    else:
        git(
            ["worktree", "add", "-b", branch, str(worktree_path), f"{REMOTE}/{MAIN_BRANCH}"],
            main_clone,
        )

    print(f"created worktree: {worktree_path}")
    print(f"branch: {branch}")
    print(f"next: cd {worktree_path}")
    return 0


def find_worktree_at_path(main_clone: Path, path: Path) -> Worktree | None:
    resolved = path.resolve()
    for worktree in parse_worktrees(main_clone):
        if worktree.path.resolve() == resolved:
            return worktree
    return None


def guard(args: argparse.Namespace) -> int:
    current = resolve_repo_root(Path.cwd())
    main_clone = require_main_clone(args.main_clone)
    worktree_root = args.worktree_root.expanduser().resolve()
    failures: list[str] = []

    if current == main_clone:
        failures.append(f"current repo is the protected main clone: {main_clone}")

    branch = current_branch(current)
    if branch == MAIN_BRANCH:
        failures.append("current branch is main")
    if not branch:
        failures.append("current checkout is detached; create a named agent branch before editing")

    if not is_relative_to(current, worktree_root):
        failures.append(f"current worktree is outside the standard root: {worktree_root}")
    else:
        relative = current.relative_to(worktree_root)
        if len(relative.parts) != 2:
            failures.append("worktree path must be <worktree-root>/<agent>/<task>")
        elif branch:
            if "/" not in branch:
                failures.append(f"branch {branch!r} must be named <agent>/<task>")
            else:
                path_agent = relative.parts[0]
                branch_agent = branch.split("/", 1)[0]
                if path_agent != branch_agent:
                    failures.append(
                        "worktree agent "
                        f"{path_agent!r} does not match branch prefix {branch_agent!r}"
                    )

    if failures:
        if args.quiet:
            print("agent worktree guard failed:", file=sys.stderr)
        else:
            print("agent worktree guard failed:")
            for failure in failures:
                print(f"- {failure}")
            print()
            print("Create a compliant worktree with:")
            print("  make agent-ensure AGENT=<agent> TASK=<task-name>")
        return 1

    if not args.quiet:
        print(f"agent worktree guard passed: {current} on {branch}")
    return 0


def ensure(args: argparse.Namespace) -> int:
    """Use the current worktree when compliant; otherwise create or reuse one."""
    resolve_policy_paths(args)
    agent_raw = getattr(args, "agent", None)
    if not agent_raw:
        raise AgentWorktreeError("ensure requires --agent (for example: codex, claude, grok)")
    task_source = (getattr(args, "task", None) or "").strip()
    if not task_source:
        raise AgentWorktreeError("ensure requires a task slug (for example: drc-package-journey)")

    current = resolve_repo_root(Path.cwd())
    guard_args = argparse.Namespace(
        main_clone=args.main_clone,
        worktree_root=args.worktree_root,
        quiet=getattr(args, "quiet", False),
    )
    if guard(guard_args) == 0:
        if not guard_args.quiet:
            print(f"agent worktree ensure: already compliant at {current}")
            print(f"branch: {current_branch(current)}")
        return 0

    main_clone = require_main_clone(args.main_clone)
    agent = slugify(agent_raw, label="agent")
    task = slugify(task_source.split("/", 1)[-1], label="task")
    branch = getattr(args, "branch", None) or f"{agent}/{task}"
    path_candidate = getattr(args, "path", None) or args.worktree_root / agent / task
    worktree_path = path_candidate.expanduser().resolve()

    existing = find_worktree_at_path(main_clone, worktree_path)
    if existing is not None:
        if not getattr(args, "quiet", False):
            print(f"agent worktree ensure: reuse existing worktree at {worktree_path}")
            print(f"branch: {existing.branch}")
            print(f"next: cd {worktree_path}")
        return 0

    if worktree_path.exists():
        raise AgentWorktreeError(
            f"worktree path exists but is not a registered git worktree: {worktree_path}; "
            "remove it or choose a different task slug"
        )

    create_args = argparse.Namespace(
        main_clone=args.main_clone,
        worktree_root=args.worktree_root,
        agent=agent,
        task=task,
        branch=branch,
        path=getattr(args, "path", None),
        no_sync=getattr(args, "no_sync", False),
    )
    if not getattr(args, "quiet", False):
        print("agent worktree ensure: creating compliant worktree")
    return create_worktree(create_args)


def hooks_path_is_installed(main_clone: Path, hooks_path_raw: str) -> bool:
    hooks_path = Path(hooks_path_raw)
    if not hooks_path.is_absolute():
        hooks_path = main_clone / hooks_path
    return hooks_path.resolve() == (main_clone / ".githooks").resolve()


def list_worktrees(args: argparse.Namespace) -> int:
    main_clone = require_main_clone(args.main_clone)
    worktree_root = args.worktree_root.expanduser().resolve()
    print(f"protected main clone: {main_clone}")
    print(f"standard worktree root: {worktree_root}")
    for worktree in parse_worktrees(main_clone):
        if worktree.path == main_clone:
            marker = "main"
        elif is_relative_to(worktree.path, worktree_root):
            marker = "standard"
        else:
            marker = "outside-standard-root"
        print(f"{marker:22} {worktree.branch:28} {worktree.path}")
    return 0


def doctor(args: argparse.Namespace) -> int:
    main_clone = require_main_clone(args.main_clone)
    worktree_root = args.worktree_root.expanduser().resolve()
    issues: list[str] = []

    print(f"protected main clone: {main_clone}")
    print(f"standard worktree root: {worktree_root}")

    branch = current_branch(main_clone)
    if branch != MAIN_BRANCH:
        issues.append(f"protected main clone is on {branch!r}, expected {MAIN_BRANCH!r}")

    dirty = status_porcelain(main_clone)
    if dirty:
        issues.append("protected main clone has local changes or untracked files")

    hooks_path_raw = git_optional_output(["config", "--get", "core.hooksPath"], main_clone)
    if hooks_path_raw:
        if not hooks_path_is_installed(main_clone, hooks_path_raw):
            issues.append(f"repo hooks path is configured to {hooks_path_raw}, expected .githooks")
    else:
        issues.append("repo hooks are not installed; run `make agent-setup`")

    for worktree in parse_worktrees(main_clone):
        if worktree.path == main_clone:
            continue
        if not is_relative_to(worktree.path, worktree_root):
            issues.append(f"worktree outside standard root: {worktree.path}")

    if issues:
        print("issues:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("agent worktree policy checks passed")
    return 0


def install_hooks(args: argparse.Namespace) -> int:
    main_clone = require_main_clone(args.main_clone)
    hooks_dir = main_clone / ".githooks"
    for hook in ("pre-commit", "pre-push"):
        hook_path = hooks_dir / hook
        if not hook_path.exists():
            raise AgentWorktreeError(f"missing hook file: {hook_path}")
        hook_path.chmod(0o755)
    git(["config", "core.hooksPath", ".githooks"], main_clone)
    git(["config", "pull.ff", "only"], main_clone)
    git(["config", "fetch.prune", "true"], main_clone)
    print("installed repo hooks and fast-forward-only pull policy")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--main-clone",
        type=Path,
        help=(
            "protected main clone; defaults to "
            f"${ENV_MAIN_CLONE}, git config {CONFIG_MAIN_CLONE}, or auto-discovery"
        ),
    )
    parser.add_argument(
        "--worktree-root",
        type=Path,
        help=(
            "agent worktree root; defaults to "
            f"${ENV_WORKTREE_ROOT}, git config {CONFIG_WORKTREE_ROOT}, "
            "or a sibling of the protected main clone"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync-main", help="fast-forward protected main clone")
    sync_parser.set_defaults(func=sync_main)

    new_parser = subparsers.add_parser("new", help="create an agent worktree and branch")
    new_parser.add_argument("task", nargs="?", help="task slug, for example drc-scenarios")
    new_parser.add_argument("--agent", required=True, help="agent name, for example codex")
    new_parser.add_argument("--branch", help="branch name; must start with <agent>/")
    new_parser.add_argument("--path", type=Path, help="explicit worktree path under the agent root")
    new_parser.add_argument("--no-sync", action="store_true", help="skip sync-main before creating")
    new_parser.set_defaults(func=create_worktree)

    guard_parser = subparsers.add_parser("guard", help="verify current checkout is safe for edits")
    guard_parser.add_argument("--quiet", action="store_true")
    guard_parser.set_defaults(func=guard)

    ensure_parser = subparsers.add_parser(
        "ensure",
        help="stay in a compliant worktree or create/reuse <worktree-root>/<agent>/<task>",
    )
    ensure_parser.add_argument("--agent", required=True, help="agent name, for example codex")
    ensure_parser.add_argument("task", nargs="?", help="task slug, for example drc-scenarios")
    ensure_parser.add_argument("--branch", help="branch name; must start with <agent>/")
    ensure_parser.add_argument("--path", type=Path, help="explicit worktree path under the agent root")
    ensure_parser.add_argument("--no-sync", action="store_true", help="skip sync-main before creating")
    ensure_parser.add_argument("--quiet", action="store_true")
    ensure_parser.set_defaults(func=ensure)

    list_parser = subparsers.add_parser("list", help="list known worktrees")
    list_parser.set_defaults(func=list_worktrees)

    doctor_parser = subparsers.add_parser("doctor", help="check local policy setup")
    doctor_parser.set_defaults(func=doctor)

    install_parser = subparsers.add_parser("install-hooks", help="install repo-managed Git hooks")
    install_parser.set_defaults(func=install_hooks)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        resolve_policy_paths(args)
        return args.func(args)
    except AgentWorktreeError as exc:
        return print_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
