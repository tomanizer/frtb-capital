"""Tests for the link-only regulatory source manifest."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "regulatory_sources.yml"
TRACEABILITY = ROOT / "docs" / "REGULATORY_TRACEABILITY.md"
SRC = ROOT / "src" / "frtb_ima"

ALLOWED_URL_PREFIXES = (
    "https://www.bis.org/",
    "https://www.govinfo.gov/",
    "https://www.occ.gov/",
    "https://eur-lex.europa.eu/",
    "https://www.eba.europa.eu/",
    "https://www.bankofengland.co.uk/",
)


def _parse_source_entries() -> list[dict[str, object]]:
    """Parse the intentionally small YAML subset used by the source manifest."""
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list: str | None = None

    for raw_line in MANIFEST.read_text().splitlines():
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
                raise AssertionError(f"Manifest key {current_list} is not a list")
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


def test_regulatory_sources_are_link_only_and_unique() -> None:
    text = MANIFEST.read_text()
    entries = _parse_source_entries()

    ids = [entry["id"] for entry in entries]
    assert len(ids) >= 10
    assert len(ids) == len(set(ids))
    assert "full_text:" not in text
    assert "text_policy:" in text
    assert "Do not vendor full regulatory text" in text


def test_regulatory_sources_use_official_urls() -> None:
    for entry in _parse_source_entries():
        url = entry.get("url")
        assert isinstance(url, str), entry
        assert url.startswith(ALLOWED_URL_PREFIXES), entry


def test_regulatory_sources_link_existing_modules_and_requirements() -> None:
    requirement_registry = (ROOT / "docs" / "requirements" / "NPR_2_0_MARKET_RISK.yml").read_text()

    for entry in _parse_source_entries():
        modules = entry.get("modules")
        requirements = entry.get("requirements")
        assert isinstance(modules, list) and modules, entry
        assert isinstance(requirements, list) and requirements, entry

        for module_path in modules:
            assert isinstance(module_path, str)
            assert (ROOT / module_path).exists(), entry
        for requirement_id in requirements:
            assert isinstance(requirement_id, str)
            assert requirement_id in requirement_registry, entry


def test_traceability_document_points_to_source_manifest() -> None:
    assert "docs/regulatory_sources.yml" in TRACEABILITY.read_text()


def test_source_modules_appear_in_traceability_table() -> None:
    traceability = TRACEABILITY.read_text()

    module_names = sorted(path.name for path in SRC.glob("*.py") if path.name != "__init__.py")
    assert module_names
    for module_name in module_names:
        assert f"| `{module_name}` |" in traceability
