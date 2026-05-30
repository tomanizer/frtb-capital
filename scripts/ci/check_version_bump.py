"""Guard: fail if any package version changed outside a release branch.

Per ADR 0015, version bumps in packages/*/pyproject.toml are only allowed
on branches matching release/*.  Feature and fix PRs must not touch version
numbers; that work belongs in the release PR.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _head_ref() -> str:
    return os.environ.get("GITHUB_HEAD_REF", "")


def _base_sha() -> str:
    """Best-effort base SHA for the diff."""
    import json

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        payload = json.loads(Path(event_path).read_text())
        sha = payload.get("pull_request", {}).get("base", {}).get("sha", "")
        if sha:
            return sha
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    return f"origin/{base_ref}"


def _changed_pyproject_files(base: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [
        p
        for p in result.stdout.splitlines()
        if p.startswith("packages/") and p.endswith("/pyproject.toml")
    ]


def _version_at(ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    m = _VERSION_RE.search(result.stdout)
    return m.group(1) if m else None


def main() -> int:
    head_ref = _head_ref()

    # Only enforce on pull_request events; skip push-to-main and schedule.
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event != "pull_request":
        print("version-bump-guard: skipping (not a pull_request event)")
        return 0

    # Release branches are exempt — they're allowed to bump versions.
    if head_ref.startswith("release/"):
        print(f"version-bump-guard: skipping release branch {head_ref!r}")
        return 0

    base = _base_sha()
    changed = _changed_pyproject_files(base)
    if not changed:
        print("version-bump-guard: no package pyproject.toml files changed")
        return 0

    violations: list[str] = []
    for path in changed:
        before = _version_at(base, path)
        after = _version_at("HEAD", path)
        if before is not None and after is not None and before != after:
            violations.append(f"  {path}: {before!r} → {after!r}")

    if violations:
        print(
            "version-bump-guard: version changed in a non-release PR\n"
            "\n"
            "Per ADR 0015, version bumps belong in a release/* PR, not in\n"
            "feature or fix PRs.  Remove the version change from this PR;\n"
            "a release PR will assign the version when these changes are\n"
            "assembled for release.\n"
            "\n"
            "Violations:",
            file=sys.stderr,
        )
        for v in violations:
            print(v, file=sys.stderr)
        return 1

    print(f"version-bump-guard: OK ({len(changed)} pyproject.toml file(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
