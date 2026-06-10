"""Run all package-level demonstration scripts with concise summaries."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RUNNER = ("uv", "run", "python")
SUMMARY_KEYWORDS = (
    "total",
    "capital",
    "demo complete",
    "positions",
    "as designed",
    "workflow summary",
    "jurisdiction",
    "method components",
)


@dataclass(frozen=True)
class DemoResult:
    """Captured result for one package demo run."""

    package: str
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """Return whether the demo process exited cleanly."""

        return self.returncode == 0


def repository_root() -> Path:
    """Return the repository root based on this script location."""

    return Path(__file__).resolve().parents[1]


def discover_demo_scripts(root: Path) -> tuple[Path, ...]:
    """Find package demo scripts in deterministic package-name order."""

    return tuple(sorted(root.glob("packages/*/examples/run_demo.py")))


def package_name(demo_script: Path) -> str:
    """Return the package directory name for a demo script path."""

    return demo_script.parts[-3]


def runner_from_env() -> tuple[str, ...]:
    """Return the configured demo command runner."""

    configured = os.environ.get("FRTB_DEMO_RUNNER")
    if not configured:
        return DEFAULT_RUNNER
    runner = tuple(shlex.split(configured))
    if not runner:
        raise ValueError("FRTB_DEMO_RUNNER must not be empty")
    return runner


def shell_join(command: Sequence[str]) -> str:
    """Render a command tuple for copyable terminal output."""

    return " ".join(shlex.quote(part) for part in command)


def summary_lines(output: str, *, limit: int = 10) -> tuple[str, ...]:
    """Select stable, high-signal lines from demo stdout."""

    lines = tuple(line.strip() for line in output.splitlines() if line.strip())
    selected: list[str] = []
    for line in lines:
        lower = line.lower()
        if any(keyword in lower for keyword in SUMMARY_KEYWORDS) and line not in selected:
            selected.append(line)
        if len(selected) >= limit:
            break
    if selected:
        return tuple(selected)
    return lines[:limit]


def run_demo(root: Path, demo_script: Path, runner: Sequence[str]) -> DemoResult:
    """Run one demo script and capture its output."""

    relative_demo = demo_script.relative_to(root)
    command = (*runner, str(relative_demo))
    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return DemoResult(
        package=package_name(demo_script),
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def print_result(result: DemoResult, *, summary_limit: int) -> None:
    """Print a deterministic summary for one demo result."""

    status = "ok" if result.passed else f"failed ({result.returncode})"
    print(f"\n== {result.package} ==")
    print(f"command: {shell_join(result.command)}")
    print(f"status: {status}")
    for line in summary_lines(result.stdout, limit=summary_limit):
        print(f"  {line}")
    if not result.passed and result.stderr.strip():
        print("stderr:")
        for line in result.stderr.strip().splitlines():
            print(f"  {line}")


def run_all(root: Path, runner: Sequence[str], *, summary_limit: int) -> int:
    """Run all discovered package demos and return a process exit code."""

    demos = discover_demo_scripts(root)
    if not demos:
        print("No package demos found.")
        return 1

    print(f"Running {len(demos)} package demos with {shell_join(runner)}")
    failures = 0
    for demo_script in demos:
        result = run_demo(root, demo_script, runner)
        print_result(result, summary_limit=summary_limit)
        failures += int(not result.passed)

    if failures:
        print(f"\nDemo check failed: {failures} package demo(s) failed.")
        return 1
    print("\nDemo check passed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running package demos."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=repository_root(),
        help="repository root containing packages/",
    )
    parser.add_argument(
        "--summary-lines",
        type=int,
        default=10,
        help="maximum summary lines to print per package",
    )
    args = parser.parse_args(argv)

    if args.summary_lines < 1:
        parser.error("--summary-lines must be at least 1")

    return run_all(args.root.resolve(), runner_from_env(), summary_limit=args.summary_lines)


if __name__ == "__main__":
    sys.exit(main())
