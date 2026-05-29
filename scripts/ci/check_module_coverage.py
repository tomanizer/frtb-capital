"""Enforce per-module coverage floors from coverage.py JSON output."""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("docs/quality/package_maturity.toml")
DEFAULT_EXCLUDES = ("demo_data.py",)


@dataclass(frozen=True)
class CoverageTarget:
    """One implemented package source tree that must meet the coverage floor."""

    package: str
    import_name: str
    source_root: Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument(
        "--source-root",
        type=Path,
        action="append",
        default=[],
        help="Explicit source root to check. Defaults to implemented packages in the registry.",
    )
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--floor", type=float, default=90.0)
    parser.add_argument("--exclude", action="append", default=list(DEFAULT_EXCLUDES))
    args = parser.parse_args(argv)

    report = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    files: dict[str, Any] = report["files"]
    excluded_names = set(args.exclude)
    targets = (
        tuple(
            CoverageTarget(
                package=source_root.parent.parent.name,
                import_name=source_root.name,
                source_root=source_root,
            )
            for source_root in args.source_root
        )
        if args.source_root
        else implemented_coverage_targets(args.registry, selected_packages=set(args.package))
    )

    if not targets:
        print("No implemented package coverage targets found.")
        return 1

    measured: list[tuple[Path, float]] = []
    missing_report_entries: list[Path] = []
    missing_or_empty_source_roots: list[Path] = []
    for target in targets:
        source_root = target.source_root.resolve()
        source_files = [
            path for path in sorted(source_root.glob("*.py")) if path.name not in excluded_names
        ]
        if not source_files:
            missing_or_empty_source_roots.append(source_root)
            continue
        for source_file in source_files:
            report_key = _coverage_key_for(source_file, files)
            if report_key is None:
                missing_report_entries.append(source_file)
                continue
            percent = float(files[report_key]["summary"]["percent_covered"])
            measured.append((source_file, percent))

    failures = [(path, percent) for path, percent in measured if percent < args.floor]
    for path, percent in measured:
        print(f"{path.relative_to(Path.cwd())}: {percent:.2f}%")

    if missing_or_empty_source_roots:
        print("Missing or empty source roots:")
        for path in missing_or_empty_source_roots:
            print(f"  {path.relative_to(Path.cwd())}")
    if missing_report_entries:
        print("Missing coverage entries:")
        for path in missing_report_entries:
            print(f"  {path.relative_to(Path.cwd())}")
    if failures:
        print(f"Modules below {args.floor:.2f}% coverage:")
        for path, percent in failures:
            print(f"  {path.relative_to(Path.cwd())}: {percent:.2f}%")
    if missing_or_empty_source_roots or missing_report_entries or failures:
        return 1

    print(f"All measured modules meet the {args.floor:.2f}% coverage floor.")
    return 0


def implemented_coverage_targets(
    registry_path: Path = REGISTRY_PATH,
    *,
    selected_packages: set[str] | None = None,
    root: Path | None = None,
) -> tuple[CoverageTarget, ...]:
    """Return source roots for implemented packages in the maturity registry."""

    root = root or Path.cwd()
    selected = selected_packages or set()
    data = tomllib.loads((root / registry_path).read_text(encoding="utf-8"))
    targets: list[CoverageTarget] = []
    for raw_package in data.get("packages", []):
        if raw_package.get("maturity") != "implemented":
            continue
        package = str(raw_package["package"])
        if selected and package not in selected:
            continue
        import_name = str(raw_package["import_name"])
        package_path = Path(str(raw_package["path"]))
        targets.append(
            CoverageTarget(
                package=package,
                import_name=import_name,
                source_root=root / package_path / "src" / import_name,
            )
        )
    return tuple(targets)


def _coverage_key_for(source_file: Path, files: dict[str, object]) -> str | None:
    resolved = source_file.resolve()
    for key in files:
        candidate = Path(key)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if candidate.resolve() == resolved:
            return key
    return None


if __name__ == "__main__":
    raise SystemExit(main())
