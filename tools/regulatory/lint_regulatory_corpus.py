from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs" / "regulatory" / "sources.yml"
CROSSWALK_DIR = ROOT / "docs" / "regulatory" / "crosswalk"
REGIME_DIR = ROOT / "docs" / "regulatory" / "regimes"

ALLOWED_SOURCE_STATUS = {
    "final_rule",
    "in_force",
    "baseline_standard",
    "supervisory_expectation",
    "technical_standard",
    "consultation",
    "proposed_rule",
    "near_final",
    "historical",
    "challenger_reference",
    "placeholder",
}


def scalar_field(block: list[str], field: str) -> str | None:
    prefix = f"    {field}:"
    for line in block:
        if line.startswith(prefix):
            value = line.split(":", 1)[1].strip()
            return value.strip('"') or None
    return None


def source_blocks() -> dict[str, list[str]]:
    lines = SOURCES.read_text(encoding="utf-8").splitlines()
    blocks: dict[str, list[str]] = {}
    current_id: str | None = None
    current: list[str] = []

    for line in lines:
        if line.startswith("  - id: "):
            if current_id is not None:
                blocks[current_id] = current
            current_id = line.split(":", 1)[1].strip()
            current = [line]
        elif current_id is not None:
            current.append(line)

    if current_id is not None:
        blocks[current_id] = current
    return blocks


def collect_source_ids(errors: list[str]) -> set[str]:
    blocks = source_blocks()
    seen: set[str] = set()

    for source_id, block in blocks.items():
        if source_id in seen:
            errors.append(f"duplicate source id: {source_id}")
        seen.add(source_id)

        status = scalar_field(block, "status")
        if status not in ALLOWED_SOURCE_STATUS:
            errors.append(f"{source_id}: invalid status {status!r}")

        for required_field in ("issuer", "jurisdiction", "title", "url"):
            if not scalar_field(block, required_field):
                errors.append(f"{source_id}: missing {required_field}")

    if not seen:
        errors.append("docs/regulatory/sources.yml: no source ids found")
    return seen


def list_values_after_key(path: Path, key: str) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: list[str] = []
    collecting = False
    list_indent: int | None = None

    for line in lines:
        stripped = line.strip()
        if stripped == f"{key}:":
            collecting = True
            list_indent = None
            continue

        if not collecting:
            continue

        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())
        if stripped.startswith("- "):
            if list_indent is None:
                list_indent = indent
            if indent >= list_indent:
                values.append(stripped[2:].strip())
                continue

        if list_indent is not None and indent <= max(list_indent - 2, 0):
            collecting = False
        elif list_indent is None and not stripped.startswith("- "):
            collecting = False

    return values


def check_references(source_ids: set[str], errors: list[str]) -> None:
    for path in sorted(CROSSWALK_DIR.glob("*.yml")):
        for ref in list_values_after_key(path, "source_refs"):
            if ref not in source_ids:
                errors.append(f"{path}: references unknown source id {ref}")

    for path in sorted(REGIME_DIR.glob("*.yml")):
        for ref in list_values_after_key(path, "primary_sources"):
            if ref not in source_ids:
                errors.append(f"{path}: references unknown primary source id {ref}")


def main() -> int:
    errors: list[str] = []
    try:
        source_ids = collect_source_ids(errors)
        check_references(source_ids, errors)
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("regulatory corpus lint: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
