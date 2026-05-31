"""Enforce killed-only mutation score floors from mutmut CI stats."""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("docs/quality/package_maturity.toml")

DEFAULT_STATS_PATHS = {
    "frtb-ima": Path("dist/mutation/frtb-ima/mutmut-cicd-stats.json"),
    "frtb-rrao": Path("dist/mutation/frtb-rrao/mutmut-cicd-stats.json"),
}

MUTATION_PREREQ_HINTS = {
    "frtb-ima": "make mutation",
    "frtb-rrao": "make mutation-rrao",
}


def _floors_from_registry(registry_path: Path = REGISTRY_PATH) -> dict[str, float]:
    """Read mutation_floor values from package_maturity.toml."""
    try:
        data = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {
        pkg["package"]: float(pkg["mutation_floor"])
        for pkg in data.get("packages", [])
        if "mutation_floor" in pkg
    }


@dataclass(frozen=True)
class MutationScoreResult:
    """Killed-only mutation score result for one package."""

    package: str
    stats_path: Path
    killed: int
    total: int
    score: float
    floor: float
    passed: bool
    error: str | None = None

    @property
    def failed_requirement_ids(self) -> tuple[str, ...]:
        if self.passed:
            return ()
        if self.error is not None:
            return ("mutation-stats-readable",)
        return ("mutation-score-floor",)


def check_stats_file(package: str, stats_path: Path, *, floor: float) -> MutationScoreResult:
    """Read one mutmut CI stats file and compare killed-only score to a floor."""

    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        if not isinstance(stats, dict):
            raise ValueError("stats must be a dictionary")
        killed = _required_int(stats, "killed")
        total = _required_int(stats, "total")
        if total <= 0:
            raise ValueError("total must be positive")
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        error = str(exc)
        if isinstance(exc, OSError):
            hint = MUTATION_PREREQ_HINTS.get(package)
            if hint is not None:
                error = (
                    f"{exc}; run `{hint}` to export mutmut-cicd-stats.json, "
                    "then re-run `make mutation-score-check`"
                )
        return MutationScoreResult(
            package=package,
            stats_path=stats_path,
            killed=0,
            total=0,
            score=0.0,
            floor=floor,
            passed=False,
            error=error,
        )

    score = killed / total * 100
    documented_score = round(score, 2)
    return MutationScoreResult(
        package=package,
        stats_path=stats_path,
        killed=killed,
        total=total,
        score=score,
        floor=floor,
        passed=documented_score >= floor,
    )


def write_json_report(results: tuple[MutationScoreResult, ...], path: Path) -> None:
    """Write deterministic mutation score evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results_to_jsonable(results), indent=2) + "\n", encoding="utf-8")


def results_to_jsonable(results: tuple[MutationScoreResult, ...]) -> dict[str, object]:
    """Return a JSON-ready result shape."""

    return {
        "packages": [
            {
                "package": result.package,
                "stats_path": str(result.stats_path),
                "killed": result.killed,
                "total": result.total,
                "score": round(result.score, 4),
                "floor": result.floor,
                "passed": result.passed,
                "failed_requirement_ids": list(result.failed_requirement_ids),
                "error": result.error,
            }
            for result in results
        ]
    }


def _required_int(stats: dict[str, Any], key: str) -> int:
    value = stats.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _parse_package_mapping(raw_values: list[str], *, option: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_value in raw_values:
        package, separator, value = raw_value.partition("=")
        package = package.strip()
        value = value.strip()
        if not separator or not package or not value:
            raise ValueError(f"{option} must use PACKAGE=VALUE form: {raw_value}")
        parsed[package] = value
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stats",
        action="append",
        default=[],
        help="Mutation stats path in PACKAGE=PATH form. Defaults to implemented baselines.",
    )
    parser.add_argument(
        "--floor",
        action="append",
        default=[],
        help="Killed-only score floor in PACKAGE=PERCENT form.",
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    try:
        stats_paths = {
            package: Path(path)
            for package, path in _parse_package_mapping(args.stats, option="--stats").items()
        } or DEFAULT_STATS_PATHS
        cli_floors = {
            package: float(value)
            for package, value in _parse_package_mapping(args.floor, option="--floor").items()
        }
    except ValueError as exc:
        print(exc)
        return 2

    registry_floors = _floors_from_registry()
    # CLI --floor overrides registry, registry overrides 0.0 sentinel.
    resolved_floors = {**registry_floors, **cli_floors}

    results = tuple(
        check_stats_file(
            package,
            stats_path,
            floor=resolved_floors.get(package, 0.0),
        )
        for package, stats_path in sorted(stats_paths.items())
    )

    if args.json_output is not None:
        write_json_report(results, args.json_output)

    for result in results:
        if result.error is not None:
            print(f"{result.package}: failed to read {result.stats_path}: {result.error}")
        else:
            print(
                f"{result.package}: killed-only score {result.score:.2f}% "
                f"({result.killed}/{result.total}), floor {result.floor:.2f}%"
            )
            if not result.passed:
                print(f"{result.package}: failed mutation score floor")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
