"""Compare benchmark JSON artifacts against documented regression budgets."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGETS = Path("docs/quality/benchmark_budgets.toml")


@dataclass(frozen=True)
class MetricBudget:
    """One numeric benchmark metric threshold."""

    name: str
    path: tuple[str, ...]
    metric_max: float | None = None
    metric_min: float | None = None


@dataclass(frozen=True)
class RequiredPath:
    """One benchmark report path that must exist."""

    name: str
    path: tuple[str, ...]


@dataclass(frozen=True)
class PathEquality:
    """Two benchmark report paths that must carry identical values."""

    name: str
    left_path: tuple[str, ...]
    right_path: tuple[str, ...]


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
    metrics: tuple[MetricBudget, ...] = ()
    required_paths: tuple[RequiredPath, ...] = ()
    path_equalities: tuple[PathEquality, ...] = ()


def load_budgets(
    path: Path = DEFAULT_BUDGETS,
    *,
    root: Path | None = None,
) -> tuple[BenchmarkBudget, ...]:
    root = root or ROOT
    data = tomllib.loads((root / path).read_text(encoding="utf-8"))
    schema_version = int(data.get("schema_version", 1))
    if schema_version not in {1, 2}:
        raise ValueError(f"unsupported benchmark budget schema_version: {schema_version}")
    budgets: list[BenchmarkBudget] = []
    for raw in data.get("benchmarks", []):
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
                metrics=_load_metric_budgets(raw),
                required_paths=_load_required_paths(raw),
                path_equalities=_load_path_equalities(raw),
            )
        )
    return tuple(budgets)


def _load_metric_budgets(raw: dict[str, Any]) -> tuple[MetricBudget, ...]:
    metrics: list[MetricBudget] = []
    legacy_path = tuple(str(part) for part in raw.get("metric_path", ()))
    if legacy_path:
        metrics.append(
            MetricBudget(
                name=".".join(legacy_path),
                path=legacy_path,
                metric_max=float(raw["metric_max"]) if "metric_max" in raw else None,
                metric_min=float(raw["metric_min"]) if "metric_min" in raw else None,
            )
        )
    raw_metrics = cast("list[dict[str, Any]]", raw.get("metrics", ()))
    for index, metric in enumerate(raw_metrics):
        if not isinstance(metric, dict):
            raise ValueError("benchmark metrics entries must be tables")
        path = tuple(str(part) for part in metric.get("path", ()))
        if not path:
            raise ValueError("benchmark metric is missing path")
        metrics.append(
            MetricBudget(
                name=str(metric.get("name", ".".join(path) or f"metric-{index}")),
                path=path,
                metric_max=float(metric["max"]) if "max" in metric else None,
                metric_min=float(metric["min"]) if "min" in metric else None,
            )
        )
    return tuple(metrics)


def _load_required_paths(raw: dict[str, Any]) -> tuple[RequiredPath, ...]:
    required_paths: list[RequiredPath] = []
    for index, required_path in enumerate(
        cast("list[dict[str, Any]]", raw.get("required_paths", ()))
    ):
        if not isinstance(required_path, dict):
            raise ValueError("benchmark required_paths entries must be tables")
        path = tuple(str(part) for part in required_path.get("path", ()))
        if not path:
            raise ValueError("benchmark required_path is missing path")
        required_paths.append(
            RequiredPath(
                name=str(required_path.get("name", ".".join(path) or f"path-{index}")),
                path=path,
            )
        )
    return tuple(required_paths)


def _load_path_equalities(raw: dict[str, Any]) -> tuple[PathEquality, ...]:
    equalities: list[PathEquality] = []
    for index, equality in enumerate(cast("list[dict[str, Any]]", raw.get("path_equalities", ()))):
        if not isinstance(equality, dict):
            raise ValueError("benchmark path_equalities entries must be tables")
        left_path = tuple(str(part) for part in equality.get("left_path", ()))
        right_path = tuple(str(part) for part in equality.get("right_path", ()))
        if not left_path or not right_path:
            raise ValueError("benchmark path_equality is missing left_path or right_path")
        equalities.append(
            PathEquality(
                name=str(equality.get("name", f"path-equality-{index}")),
                left_path=left_path,
                right_path=right_path,
            )
        )
    return tuple(equalities)


def _read_path(report: dict[str, object], path: tuple[str, ...]) -> object:
    current: object = report
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"path {path!r} is not present")
        current = current[key]
    return current


def _read_metric(report: dict[str, object], path: tuple[str, ...]) -> float:
    current = _read_path(report, path)
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

    for required_path in budget.required_paths:
        try:
            _read_path(report, required_path.path)
        except ValueError as exc:
            return [f"{budget.name}: required path {required_path.name}: {exc}"]

    for metric in budget.metrics:
        try:
            metric_value = _read_metric(report, metric.path)
        except ValueError as exc:
            return [f"{budget.name}: {exc}"]
        joined = ".".join(metric.path)
        if metric.metric_max is not None and metric_value > metric.metric_max:
            errors.append(
                f"{budget.name}: {joined} {metric_value:.2f} exceeds budget {metric.metric_max:.2f}"
            )
        if metric.metric_min is not None and metric_value < metric.metric_min:
            errors.append(
                f"{budget.name}: {joined} {metric_value:.2f} below budget {metric.metric_min:.2f}"
            )

    for equality in budget.path_equalities:
        try:
            left = _read_path(report, equality.left_path)
            right = _read_path(report, equality.right_path)
        except ValueError as exc:
            return [f"{budget.name}: path equality {equality.name}: {exc}"]
        if left != right:
            errors.append(
                f"{budget.name}: path equality {equality.name} failed: "
                f"{'.'.join(equality.left_path)} != {'.'.join(equality.right_path)}"
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
