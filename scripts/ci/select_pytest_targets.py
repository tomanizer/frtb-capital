"""Select focused pytest targets for changed-path PR checks."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import classify_changed_paths

FULL_TEST_TARGETS = ("packages", "tests")
SCRIPT_TEST_TARGETS = ("tests", "packages/frtb-common/tests")


def _git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def _local_changed_paths(base_ref: str) -> set[str]:
    diff_base = _git_lines(["merge-base", base_ref, "HEAD"])
    paths: set[str] = set()
    if diff_base:
        paths.update(_git_lines(["diff", "--name-only", f"{diff_base[0]}...HEAD"]))
    else:
        paths.update(_git_lines(["diff", "--name-only", base_ref, "HEAD"]))

    paths.update(_git_lines(["diff", "--name-only"]))
    paths.update(_git_lines(["diff", "--cached", "--name-only"]))
    paths.update(_git_lines(["ls-files", "--others", "--exclude-standard"]))
    return paths


def _changed_paths(base_ref: str) -> set[str]:
    event_name, paths = classify_changed_paths._changed_paths()
    if event_name:
        return paths
    return _local_changed_paths(base_ref)


def select_targets(paths: Iterable[str]) -> tuple[str, ...]:
    selected: set[str] = set()
    force_full = False

    for path in paths:
        if path in {"Makefile", "pyproject.toml", "uv.lock"} or path.endswith("/pyproject.toml"):
            force_full = True
            continue
        if path.startswith(".github/workflows/"):
            force_full = True
            continue
        if path.startswith("packages/frtb-common/src/") or path.startswith(
            "packages/frtb-common/tests/"
        ):
            force_full = True
            continue
        if path.startswith("packages/"):
            parts = Path(path).parts
            if len(parts) >= 3 and ("src" in parts or "tests" in parts):
                selected.add(f"packages/{parts[1]}/tests")
            continue
        if path.startswith("scripts/") and path.endswith(".py"):
            selected.update(SCRIPT_TEST_TARGETS)
            continue
        if path.startswith("tests/") and not path.endswith((".md", ".yml", ".yaml", ".ipynb")):
            selected.add("tests")

    if force_full:
        return FULL_TEST_TARGETS
    return tuple(sorted(selected))


def _write_github_output(targets: tuple[str, ...]) -> None:
    output_path = Path.cwd() / ".github-output"
    if "GITHUB_OUTPUT" in os.environ:
        output_path = Path(os.environ["GITHUB_OUTPUT"])
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"targets={' '.join(targets)}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", default="origin/main", help="base ref for local changed-path runs"
    )
    parser.add_argument(
        "--github-output", action="store_true", help="write targets to GITHUB_OUTPUT"
    )
    parser.add_argument("--run", action="store_true", help="run pytest for the selected targets")
    args = parser.parse_args(argv)

    paths = _changed_paths(args.base)
    targets = select_targets(paths)

    if args.github_output:
        _write_github_output(targets)
    else:
        print(" ".join(targets), flush=True)

    if args.run:
        if not targets:
            print("No changed pytest targets selected.")
            return 0
        return subprocess.run(["uv", "run", "pytest", *targets], check=False).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
