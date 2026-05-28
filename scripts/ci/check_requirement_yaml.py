"""Validate lightweight requirement-registry YAML files.

This is intentionally a small structural check for the repository's requirement
registries. It does not try to be a general YAML parser.
"""

from __future__ import annotations

from pathlib import Path

BASE_REQUIRED_KEYS = {"id", "title", "source", "status", "notes"}
IMPLEMENTATION_STATUSES = {"implemented", "partial", "planned"}


def _registry_paths(root: Path) -> list[Path]:
    return sorted(
        [
            *root.glob("docs/modules/*/requirements/*.yml"),
            *root.glob("packages/*/docs/requirements/*.yml"),
        ]
    )


def _inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]


def _status_values(lines: list[str]) -> set[str]:
    values: list[str] = []
    for index, line in enumerate(lines):
        if line.startswith("status_values:"):
            inline = _inline_list(line.split(":", 1)[1])
            if inline:
                values.extend(inline)
                break
            for child in lines[index + 1 :]:
                if child.startswith("  - "):
                    values.append(child.strip()[2:].strip().strip("'\""))
                    continue
                if child and not child.startswith(" "):
                    break
            break
    return set(values)


def _requirement_entries(lines: list[str]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list: str | None = None
    in_requirements = False

    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line == "requirements:":
            in_requirements = True
            continue
        if not in_requirements:
            continue
        if raw_line.startswith("  - id: "):
            if current is not None:
                entries.append(current)
            current = {"id": raw_line.split(":", 1)[1].strip().strip("'\"")}
            current_list = None
            continue
        if current is None:
            continue
        if not raw_line.startswith("    "):
            current_list = None
            continue
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            if current_list is None:
                raise AssertionError(f"list item without parent key: {raw_line}")
            current.setdefault(current_list, []).append(stripped[2:].strip().strip("'\""))  # type: ignore[union-attr]
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        value = value.strip()
        if value == "":
            current[key] = []
            current_list = key
        else:
            current[key] = _inline_list(value) or value.strip("'\"")
            current_list = None

    if current is not None:
        entries.append(current)
    return entries


def _validate_registry(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    for key in ("schema_version:", "name:", "status_values:", "requirements:"):
        if not any(line.startswith(key) for line in lines):
            errors.append(f"missing top-level {key.rstrip(':')}")

    statuses = _status_values(lines)
    if not statuses:
        errors.append("missing status_values entries")

    try:
        entries = _requirement_entries(lines)
    except AssertionError as exc:
        return [str(exc)]

    if not entries:
        errors.append("missing requirements entries")
    ids = [str(entry.get("id", "")) for entry in entries]
    if len(ids) != len(set(ids)):
        errors.append("duplicate requirement IDs")

    for entry in entries:
        req_id = entry.get("id", "<missing id>")
        missing = BASE_REQUIRED_KEYS.difference(entry)
        if missing:
            errors.append(f"{req_id}: missing keys {', '.join(sorted(missing))}")
        status = entry.get("status")
        if statuses and status not in statuses:
            errors.append(f"{req_id}: invalid status {status!r}")
        if status not in IMPLEMENTATION_STATUSES:
            continue
        for key in ("modules", "tests"):
            value = entry.get(key)
            if not isinstance(value, list) or not value:
                errors.append(f"{req_id}: {key} must be a non-empty list")
    return errors


def main() -> None:
    root = Path.cwd()
    registries = _registry_paths(root)
    errors: list[str] = []
    for path in registries:
        for error in _validate_registry(path):
            errors.append(f"{path}: {error}")

    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    print(f"checked {len(registries)} requirement registries")


if __name__ == "__main__":
    main()
