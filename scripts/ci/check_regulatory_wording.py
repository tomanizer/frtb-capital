"""Flag uncited regulatory wording such as 'working assumption' in docs and notebooks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_GLOBS = (
    "docs/**/*.md",
    "packages/**/notebooks/**/*.ipynb",
    "packages/**/src/**/*.py",
)

ALLOWLIST_SUFFIXES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CHANGELOG.md",
)

ALLOWLIST_PATHS = {
    Path("docs/quality/QUALITY_CONTROL_PLANE_REQUIREMENTS.md"),
    Path("tests/quality/test_regulatory_wording.py"),
}

WORKING_ASSUMPTION_PATTERN = re.compile(r"working assumptions?", re.IGNORECASE)


def _is_allowlisted(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if relative in ALLOWLIST_PATHS:
        return True
    if relative.name in ALLOWLIST_SUFFIXES:
        return True
    if relative.parts and relative.parts[0] == "tests":
        return True
    return False


def _iter_scan_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and not _is_allowlisted(path):
                files.add(path)
    return sorted(files)


def _line_matches(text: str) -> bool:
    if not WORKING_ASSUMPTION_PATTERN.search(text):
        return False
    lowered = text.lower()
    if "do not use" in lowered or "not to use" in lowered:
        return False
    if "instead of" in lowered and "working assumption" in lowered:
        return False
    if "replaced misleading regulatory" in lowered:
        return False
    return True


def _notebook_lines(path: Path) -> list[tuple[int, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    lines: list[tuple[int, str]] = []
    for cell_index, cell in enumerate(payload.get("cells", []), start=1):
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", [])
        if isinstance(source, str):
            source_lines = source.splitlines()
        else:
            source_lines = [str(line) for line in source]
        for line_index, line in enumerate(source_lines, start=1):
            lines.append((cell_index * 1000 + line_index, line))
    return lines


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return offending line numbers and text for one file."""

    if path.suffix == ".ipynb":
        iterable = _notebook_lines(path)
    else:
        iterable = [
            (index, line.rstrip("\n"))
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        ]

    return [(line_no, line) for line_no, line in iterable if _line_matches(line)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    errors: list[str] = []
    for path in _iter_scan_files():
        relative = path.relative_to(ROOT)
        for line_no, line in scan_file(path):
            errors.append(f"{relative}:{line_no}: {line.strip()}")

    if errors:
        print(
            "ERROR: uncited 'working assumption' wording found. "
            "Use explicit regulatory paragraph citations or limitation language.",
            file=sys.stderr,
        )
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("regulatory wording lint: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
