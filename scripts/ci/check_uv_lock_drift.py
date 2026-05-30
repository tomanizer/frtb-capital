"""Guard: fail if uv.lock changed without a corresponding dependency-spec change.

Per ADR 0015, uv.lock should only change in a PR when the PR itself modifies
dependency specifications (project.dependencies, dependency-groups, or
tool.uv.sources).  A stale or gratuitous lock regeneration causes merge
conflicts for every concurrent PR and should be caught before merge.

Release branches (release/*) are exempt because they intentionally bump
versions and regenerate the lock.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


_DEP_SECTION_RE = re.compile(
    r"^\[(?:project\.dependencies|dependency-groups|tool\.uv\.sources)\]",
    re.MULTILINE,
)


def _head_ref() -> str:
    return os.environ.get("GITHUB_HEAD_REF", "")


def _base_sha() -> str:
    import json

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        payload = json.loads(Path(event_path).read_text())
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


def _dep_section_changed(base: str, path: str) -> bool:
    """Return True if any dependency-specification section changed in path."""
    result = subprocess.run(
        ["git", "diff", f"{base}...HEAD", "--", path],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    diff = result.stdout
    if not diff:
        return False
    # Look for +/- lines inside a dependency section header context
    in_dep_section = False
    for line in diff.splitlines():
        if line.startswith("@@"):
            in_dep_section = False
        if _DEP_SECTION_RE.search(line.lstrip("+-")):
            in_dep_section = True
        if in_dep_section and line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            return True
    return False


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

    # Check all pyproject.toml files (root + packages) for dep-spec changes
    pyproject_files = [p for p in changed if p.endswith("pyproject.toml")]
    dep_changed = any(_dep_section_changed(base, p) for p in pyproject_files)

    if not dep_changed:
        print(
            "uv-lock-guard: uv.lock changed but no dependency specifications changed\n"
            "\n"
            "Per ADR 0015, uv.lock should only be regenerated when this PR\n"
            "modifies [project.dependencies], [dependency-groups], or\n"
            "[tool.uv.sources] in a pyproject.toml.  Gratuitous lock\n"
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
        f"changes in: {', '.join(pyproject_files)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
