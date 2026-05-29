from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs" / "regulatory" / "sources.yml"
CHALLENGERS = ROOT / "docs" / "validation" / "challenger_models.yml"
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


def clean_scalar(value: str) -> str:
    return value.split(" #", 1)[0].strip().strip("'\"")


def scalar_field(block: list[str], field: str) -> str | None:
    prefix = f"    {field}:"
    for line in block:
        if line.startswith(prefix):
            value = line.split(":", 1)[1].strip()
            return clean_scalar(value) or None
    return None


def source_blocks() -> list[tuple[str, list[str]]]:
    lines = SOURCES.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[str, list[str]]] = []
    current_id: str | None = None
    current: list[str] = []

    for line in lines:
        if line.startswith("  - id: "):
            if current_id is not None:
                blocks.append((current_id, current))
            current_id = clean_scalar(line.split(":", 1)[1])
            current = [line]
        elif current_id is not None:
            current.append(line)

    if current_id is not None:
        blocks.append((current_id, current))
    return blocks


def collect_source_ids(errors: list[str]) -> set[str]:
    seen: set[str] = set()

    for source_id, block in source_blocks():
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


def collect_challenger_ids(errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for line in CHALLENGERS.read_text(encoding="utf-8").splitlines():
        if line.startswith("  - id: "):
            challenger_id = clean_scalar(line.split(":", 1)[1])
            if challenger_id in seen:
                errors.append(f"duplicate challenger id: {challenger_id}")
            seen.add(challenger_id)

    if not seen:
        errors.append("docs/validation/challenger_models.yml: no challenger ids found")
    return seen


def list_values_after_key(path: Path, key: str) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: list[str] = []
    collecting = False
    key_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == f"{key}:":
            collecting = True
            key_indent = len(line) - len(line.lstrip())
            continue

        if not collecting:
            continue

        indent = len(line) - len(line.lstrip())
        if stripped.startswith("- "):
            values.append(clean_scalar(stripped[2:]))
            continue

        if indent <= key_indent:
            collecting = False

    return values


def check_references(source_ids: set[str], challenger_ids: set[str], errors: list[str]) -> None:
    for path in sorted(CROSSWALK_DIR.glob("*.yml")):
        for ref in list_values_after_key(path, "source_refs"):
            if ref not in source_ids:
                errors.append(f"{path}: references unknown source id {ref}")
        for ref in list_values_after_key(path, "challenger_refs"):
            if ref not in challenger_ids:
                errors.append(f"{path}: references unknown challenger id {ref}")

    for path in sorted(REGIME_DIR.glob("*.yml")):
        for ref in list_values_after_key(path, "primary_sources"):
            if ref not in source_ids:
                errors.append(f"{path}: references unknown primary source id {ref}")


def main() -> int:
    errors: list[str] = []
    try:
        source_ids = collect_source_ids(errors)
        challenger_ids = collect_challenger_ids(errors)
        check_references(source_ids, challenger_ids, errors)
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
