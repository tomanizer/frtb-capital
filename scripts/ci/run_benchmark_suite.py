"""Run benchmark report generators used by the performance gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkCommand:
    """One benchmark command and optional environment overrides."""

    args: tuple[str, ...]
    env: dict[str, str] | None = None


def _pythonpath(*paths: str) -> str:
    return os.pathsep.join(paths)


BENCHMARK_COMMANDS: dict[str, BenchmarkCommand] = {
    "ima-target-scale": BenchmarkCommand(
        (
            "uv",
            "run",
            "python",
            "scripts/benchmark_target_scale.py",
            "--output",
            "dist/benchmarks/frtb-ima-target-scale.json",
        )
    ),
    "ima-arrow-batch": BenchmarkCommand(
        (
            "uv",
            "run",
            "python",
            "benchmarks/ima_arrow_batch_harness.py",
            "--output",
            "dist/benchmarks/frtb-ima-arrow-batch.json",
        )
    ),
    "sbm": BenchmarkCommand(
        (
            "uv",
            "run",
            "python",
            "benchmarks/sbm_adapter_harness.py",
            "--output",
            "dist/benchmarks/frtb-sbm-batch-arrow.json",
        )
    ),
    "drc": BenchmarkCommand(
        (
            "uv",
            "run",
            "python",
            "benchmarks/drc_adapter_harness.py",
            "--output",
            "dist/benchmarks/frtb-drc-batch-arrow.json",
        )
    ),
    "rrao": BenchmarkCommand(
        (
            "uv",
            "run",
            "python",
            "packages/frtb-rrao/scripts/benchmark_rrao_target_scale.py",
            "--output",
            "dist/benchmarks/frtb-rrao-target-scale.json",
        ),
        env={"PYTHONPATH": _pythonpath("packages/frtb-common/src", "packages/frtb-rrao/src")},
    ),
    "cva": BenchmarkCommand(
        (
            "uv",
            "run",
            "python",
            "packages/frtb-cva/scripts/benchmark_cva_target_scale.py",
            "--output",
            "dist/benchmarks/frtb-cva-target-scale.json",
        ),
        env={"PYTHONPATH": _pythonpath("packages/frtb-common/src", "packages/frtb-cva/src")},
    ),
}

DEFAULT_BENCHMARKS = tuple(BENCHMARK_COMMANDS)


def run_benchmarks(targets: Sequence[str]) -> None:
    """Run selected benchmark commands in declaration order."""
    for target in targets:
        command = BENCHMARK_COMMANDS[target]
        env = os.environ.copy()
        if command.env:
            env.update(command.env)
        subprocess.run(command.args, check=True, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        default=None,
        nargs="*",
        help="benchmark target(s) to run; defaults to the full suite",
    )
    args = parser.parse_args(argv)
    targets = tuple(args.targets) or DEFAULT_BENCHMARKS
    unknown_targets = sorted(set(targets) - set(BENCHMARK_COMMANDS))
    if unknown_targets:
        parser.error(f"unknown benchmark target(s): {', '.join(unknown_targets)}")
    run_benchmarks(targets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
