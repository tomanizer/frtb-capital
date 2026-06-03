"""Guard: fail if uv.lock changed without a corresponding dependency-spec change.

Per ADR 0015, uv.lock should only change in a PR when the PR itself modifies
dependency specifications (project.dependencies, project.optional-dependencies,
dependency-groups, or tool.uv.sources).  A stale or gratuitous lock regeneration causes merge
conflicts for every concurrent PR and should be caught before merge.

Release branches (release/*) are exempt because they intentionally bump
versions and regenerate the lock.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


def _head_ref() -> str:
    return os.environ.get("GITHUB_HEAD_REF", "")


def _base_sha() -> str:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        sha = payload.get("pull_request", {}).get("base", {}).get("sha", "")
        if sha:
            return sha
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    return f"origin/{base_ref}"


def _changed_files(base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return set(result.stdout.splitlines())


def _file_bytes_at(ref: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _normalize_sources(sources: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(sources, dict):
        return ()
    return tuple((name, json.dumps(sources[name], sort_keys=True)) for name in sorted(sources))


def _dependency_spec_snapshot(content: bytes) -> tuple[Any, ...]:
    data = tomllib.loads(content.decode())
    project = data.get("project") or {}
    deps = tuple(project.get("dependencies") or ())
    optional_deps_raw = project.get("optional-dependencies") or {}
    optional_deps = tuple(
        (extra, tuple(sorted(specs))) for extra, specs in sorted(optional_deps_raw.items())
    )
    groups_raw = data.get("dependency-groups") or {}
    groups = tuple((group, tuple(sorted(specs))) for group, specs in sorted(groups_raw.items()))
    uv_tool = (data.get("tool") or {}).get("uv") or {}
    sources = _normalize_sources(uv_tool.get("sources"))
    return (deps, optional_deps, groups, sources)


def _dep_spec_changed(base: str, path: str) -> bool:
    """Return True if dependency specifications differ between base and HEAD."""
    before = _file_bytes_at(base, path)
    after = _file_bytes_at("HEAD", path)
    if before is None or after is None:
        return before != after
    return _dependency_spec_snapshot(before) != _dependency_spec_snapshot(after)


def _all_pyproject_files() -> list[str]:
    """Return root and package pyproject.toml paths present at HEAD."""
    paths = ["pyproject.toml"]
    packages_dir = Path("packages")
    if packages_dir.is_dir():
        paths.extend(str(path) for path in sorted(packages_dir.glob("*/pyproject.toml")))
    return paths


def main() -> int:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event != "pull_request":
        print("uv-lock-guard: skipping (not a pull_request event)")
        return 0

    head_ref = _head_ref()
    if head_ref.startswith("release/"):
        print(f"uv-lock-guard: skipping release branch {head_ref!r}")
        return 0

    base = _base_sha()
    changed = _changed_files(base)

    if "uv.lock" not in changed:
        print("uv-lock-guard: uv.lock not changed, nothing to check")
        return 0

    # Compare dependency specs for every pyproject.toml that exists at HEAD.
    # Do not limit to files in the PR diff: a lock refresh is valid when any
    # workspace manifest changes dependency-groups, project.dependencies, or
    # tool.uv.sources relative to the merge base.
    pyproject_files = _all_pyproject_files()
    dep_changed = any(_dep_spec_changed(base, path) for path in pyproject_files)
    changed_pyprojects = sorted(p for p in pyproject_files if p in changed)

    if not dep_changed:
        print(
            "uv-lock-guard: uv.lock changed but no dependency specifications changed\n"
            "\n"
            "Per ADR 0015, uv.lock should only be regenerated when this PR\n"
            "modifies [project.dependencies], [project.optional-dependencies],\n"
            "[dependency-groups], or [tool.uv.sources] in a pyproject.toml.  Gratuitous lock\n"
            "regeneration causes merge conflicts for concurrent PRs.\n"
            "\n"
            "To fix: restore uv.lock to its base state with:\n"
            "  git checkout origin/main -- uv.lock\n"
            "\n"
            "If your PR genuinely changes dependencies, ensure the\n"
            "dependency section in pyproject.toml reflects the change.",
            file=sys.stderr,
        )
        return 1

    print(
        f"uv-lock-guard: OK (uv.lock changed alongside dependency-spec "
        f"changes; changed manifests in diff: "
        f"{', '.join(changed_pyprojects) or 'none listed'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
