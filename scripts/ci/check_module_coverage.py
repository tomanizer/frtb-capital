"""Enforce per-module coverage floors from coverage.py JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("packages/frtb-ima/src/frtb_ima"),
    )
    parser.add_argument("--floor", type=float, default=90.0)
    parser.add_argument("--exclude", action="append", default=["demo_data.py"])
    args = parser.parse_args()

    report = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    files: dict[str, Any] = report["files"]
    source_root = args.source_root.resolve()
    excluded_names = set(args.exclude)

    measured: list[tuple[Path, float]] = []
    missing_report_entries: list[Path] = []
    for source_file in sorted(source_root.glob("*.py")):
        if source_file.name in excluded_names:
            continue
        report_key = _coverage_key_for(source_file, files)
        if report_key is None:
            missing_report_entries.append(source_file)
            continue
        percent = float(files[report_key]["summary"]["percent_covered"])
        measured.append((source_file, percent))

    failures = [(path, percent) for path, percent in measured if percent < args.floor]
    for path, percent in measured:
        print(f"{path.relative_to(Path.cwd())}: {percent:.2f}%")

    if missing_report_entries:
        print("Missing coverage entries:")
        for path in missing_report_entries:
            print(f"  {path.relative_to(Path.cwd())}")
    if failures:
        print(f"Modules below {args.floor:.2f}% coverage:")
        for path, percent in failures:
            print(f"  {path.relative_to(Path.cwd())}: {percent:.2f}%")
    if missing_report_entries or failures:
        return 1

    print(f"All measured modules meet the {args.floor:.2f}% coverage floor.")
    return 0


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
