"""Tests for the NPR 2.0 requirement registry."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "requirements" / "NPR_2_0_MARKET_RISK.yml"
ALLOWED_STATUSES = {"implemented", "partial", "unsupported"}


def _parse_registry_entries() -> list[dict[str, object]]:
    """Parse the intentionally small YAML subset used by the registry."""
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list: str | None = None

    for raw_line in REGISTRY.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        if raw_line.startswith("  - id: "):
            if current is not None:
                entries.append(current)
            current = {"id": raw_line.split(":", 1)[1].strip()}
            current_list = None
            continue

        if current is None or not raw_line.startswith("    "):
            current_list = None
            continue

        stripped = raw_line.strip()
        if stripped.startswith("- "):
            if current_list is None:
                raise AssertionError(f"List item without list key: {raw_line}")
            values = current.setdefault(current_list, [])
            if not isinstance(values, list):
                raise AssertionError(f"Registry key {current_list} is not a list")
            values.append(stripped[2:].strip())
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        value = value.strip()
        if value == "":
            current[key] = []
            current_list = key
        else:
            current[key] = value.strip('"')
            current_list = None

    if current is not None:
        entries.append(current)
    return entries


@pytest.fixture(scope="module")
def registry_entries() -> list[dict[str, object]]:
    return _parse_registry_entries()


def test_registry_has_unique_requirement_ids(
    registry_entries: list[dict[str, object]],
) -> None:
    ids = [entry["id"] for entry in registry_entries]
    assert len(ids) >= 20
    assert len(ids) == len(set(ids))
    assert all(isinstance(req_id, str) and req_id.startswith("NPR-MR-") for req_id in ids)


def test_registry_statuses_are_valid(
    registry_entries: list[dict[str, object]],
) -> None:
    for entry in registry_entries:
        assert entry.get("status") in ALLOWED_STATUSES, entry


def test_implemented_and_partial_requirements_have_existing_code_and_tests(
    registry_entries: list[dict[str, object]],
) -> None:
    for entry in registry_entries:
        if entry.get("status") not in {"implemented", "partial"}:
            continue

        modules = entry.get("modules")
        tests = entry.get("tests")
        assert isinstance(modules, list) and modules, entry
        assert isinstance(tests, list) and tests, entry

        for module_path in modules:
            assert isinstance(module_path, str)
            assert (ROOT / module_path).exists(), entry
        for test_path in tests:
            assert isinstance(test_path, str)
            assert (ROOT / test_path).exists(), entry


def test_unsupported_requirements_are_explicitly_documented(
    registry_entries: list[dict[str, object]],
) -> None:
    unsupported = [entry for entry in registry_entries if entry.get("status") == "unsupported"]
    assert unsupported
    for entry in unsupported:
        assert entry.get("notes"), entry
        assert entry.get("source_url"), entry


def test_core_npr_gaps_are_tracked(
    registry_entries: list[dict[str, object]],
) -> None:
    ids = {entry["id"] for entry in registry_entries}
    assert {
        "NPR-MR-RFET-002",
        "NPR-MR-NMRF-002",
        "NPR-MR-CAP-003",
        "NPR-MR-CAP-004",
        "NPR-MR-CAP-005",
        "NPR-MR-DESK-001",
    }.issubset(ids)
