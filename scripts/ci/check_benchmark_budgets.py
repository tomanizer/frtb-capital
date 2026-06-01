"""Compare benchmark JSON artifacts against documented regression budgets."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGETS = Path("docs/quality/benchmark_budgets.toml")


@dataclass(frozen=True)
class BenchmarkBudget:
    """One benchmark artifact threshold."""

    name: str
    artifact: Path
    wall_clock_path: tuple[str, ...]
    wall_clock_seconds_max: float | None = None
    baseline_artifact: Path | None = None
    baseline_wall_clock_path: tuple[str, ...] = ()
    wall_clock_tolerance_multiplier: float | None = None
    wall_clock_tolerance_seconds: float = 0.0
    metric_path: tuple[str, ...] = ()
    metric_max: float | None = None
    metric_min: float | None = None


def load_budgets(
    path: Path = DEFAULT_BUDGETS,
    *,
    root: Path | None = None,
) -> tuple[BenchmarkBudget, ...]:
    root = root or ROOT
    data = tomllib.loads((root / path).read_text(encoding="utf-8"))
    budgets: list[BenchmarkBudget] = []
    for raw in data.get("benchmarks", []):
        metric_path = tuple(str(part) for part in raw.get("metric_path", ()))
        wall_clock_path = tuple(
            str(part) for part in raw.get("wall_clock_path", ("totals", "wall_clock_seconds"))
        )
        baseline_artifact = (
            Path(str(raw["baseline_artifact"])) if "baseline_artifact" in raw else None
        )
        baseline_wall_clock_path = tuple(
            str(part) for part in raw.get("baseline_wall_clock_path", wall_clock_path)
        )
        budgets.append(
            BenchmarkBudget(
                name=str(raw["name"]),
                artifact=Path(str(raw["artifact"])),
                wall_clock_path=wall_clock_path,
                wall_clock_seconds_max=(
                    float(raw["wall_clock_seconds_max"])
                    if "wall_clock_seconds_max" in raw
                    else None
                ),
                baseline_artifact=baseline_artifact,
                baseline_wall_clock_path=baseline_wall_clock_path,
                wall_clock_tolerance_multiplier=(
                    float(raw["wall_clock_tolerance_multiplier"])
                    if "wall_clock_tolerance_multiplier" in raw
                    else None
                ),
                wall_clock_tolerance_seconds=(
                    float(raw["wall_clock_tolerance_seconds"])
                    if "wall_clock_tolerance_seconds" in raw
                    else 0.0
                ),
                metric_path=metric_path,
                metric_max=float(raw["metric_max"]) if "metric_max" in raw else None,
                metric_min=float(raw["metric_min"]) if "metric_min" in raw else None,
            )
        )
    return tuple(budgets)


def _read_metric(report: dict[str, object], path: tuple[str, ...]) -> float:
    current: object = report
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"metric path {path!r} is not present")
        current = current[key]
    if not isinstance(current, (int, float)):
        raise ValueError(f"metric at {path!r} is not numeric")
    return float(current)


def check_budget(budget: BenchmarkBudget, *, root: Path | None = None) -> list[str]:
    root = root or ROOT
    artifact_path = root / budget.artifact
    if not artifact_path.exists():
        return [
            f"{budget.name}: missing artifact {budget.artifact}; "
            f"run the benchmark command documented in docs/quality/BENCHMARK_PROFILE.md"
        ]

    try:
        report = json.loads(artifact_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{budget.name}: invalid JSON artifact: {exc}"]
    if not isinstance(report, dict):
        return [f"{budget.name}: artifact must be a JSON object"]

    errors: list[str] = []
    try:
        wall_clock = _read_metric(report, budget.wall_clock_path)
    except ValueError as exc:
        return [f"{budget.name}: {exc}"]

    wall_clock_limit_errors, wall_clock_limit = _wall_clock_limit(budget, root=root)
    if wall_clock_limit_errors:
        return wall_clock_limit_errors
    if wall_clock_limit is not None and wall_clock > wall_clock_limit:
        joined = ".".join(budget.wall_clock_path)
        errors.append(
            f"{budget.name}: {joined} {wall_clock:.2f}s exceeds budget {wall_clock_limit:.2f}s"
        )

    if budget.metric_path:
        try:
            metric_value = _read_metric(report, budget.metric_path)
        except ValueError as exc:
            return [f"{budget.name}: {exc}"]
        joined = ".".join(budget.metric_path)
        if budget.metric_max is not None and metric_value > budget.metric_max:
            errors.append(
                f"{budget.name}: {joined} {metric_value:.2f} exceeds budget {budget.metric_max:.2f}"
            )
        if budget.metric_min is not None and metric_value < budget.metric_min:
            errors.append(
                f"{budget.name}: {joined} {metric_value:.2f} below budget {budget.metric_min:.2f}"
            )

    return errors


def _wall_clock_limit(
    budget: BenchmarkBudget,
    *,
    root: Path,
) -> tuple[list[str], float | None]:
    limits: list[float] = []
    if budget.wall_clock_seconds_max is not None:
        limits.append(budget.wall_clock_seconds_max)

    if budget.baseline_artifact is not None:
        if budget.wall_clock_tolerance_multiplier is None:
            return [
                f"{budget.name}: baseline_artifact requires wall_clock_tolerance_multiplier"
            ], None
        baseline_path = root / budget.baseline_artifact
        if not baseline_path.exists():
            return [f"{budget.name}: missing baseline artifact {budget.baseline_artifact}"], None
        try:
            baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            return [f"{budget.name}: invalid baseline JSON artifact: {exc}"], None
        if not isinstance(baseline_report, dict):
            return [f"{budget.name}: baseline artifact must be a JSON object"], None
        try:
            baseline_wall_clock = _read_metric(
                baseline_report,
                budget.baseline_wall_clock_path or budget.wall_clock_path,
            )
        except ValueError as exc:
            return [f"{budget.name}: baseline {exc}"], None
        limits.append(
            baseline_wall_clock * budget.wall_clock_tolerance_multiplier
            + budget.wall_clock_tolerance_seconds
        )

    if not limits:
        return [f"{budget.name}: no wall-clock budget configured"], None
    return [], min(limits)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    args = parser.parse_args(argv)

    errors: list[str] = []
    for budget in load_budgets(args.budgets):
        errors.extend(check_budget(budget))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("benchmark budget check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
