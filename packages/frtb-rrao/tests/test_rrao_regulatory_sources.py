"""Tests for the RRAO link-only regulatory source manifest."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MANIFEST = DOCS / "regulatory_sources.yml"
TRACEABILITY = DOCS / "REGULATORY_TRACEABILITY.md"
ASSUMPTIONS = DOCS / "REGULATORY_ASSUMPTIONS.md"
PACKAGE_README = ROOT / "README.md"
MODULE_DOCS = ROOT.parents[1] / "docs" / "modules" / "frtb-rrao"

ALLOWED_URL_PREFIXES = (
    "https://www.bis.org/",
    "https://www.govinfo.gov/",
    "https://www.occ.gov/",
    "https://eur-lex.europa.eu/",
    "https://www.eba.europa.eu/",
    "https://www.legislation.gov.uk/",
    "https://www.bankofengland.co.uk/",
    "https://github.com/frtb-net/FRTB/",
)


def _parse_source_entries() -> list[dict[str, object]]:
    """Parse the intentionally small YAML subset used by the source manifest."""

    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list: str | None = None

    for raw_line in MANIFEST.read_text(encoding="utf-8").splitlines():
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
    text = MANIFEST.read_text(encoding="utf-8")
    entries = _parse_source_entries()

    ids = [entry["id"] for entry in entries]
    assert len(ids) >= 8
    assert len(ids) == len(set(ids))
    assert "full_text:" not in text
    assert "text_policy:" in text
    assert "Do not vendor full regulatory text" in text


def test_regulatory_sources_use_allowed_urls() -> None:
    for entry in _parse_source_entries():
        url = entry.get("url")
        assert isinstance(url, str), entry
        assert url.startswith(ALLOWED_URL_PREFIXES), entry


def test_regulatory_docs_cross_link_manifest_and_model_front_door() -> None:
    traceability = TRACEABILITY.read_text(encoding="utf-8")
    assumptions = ASSUMPTIONS.read_text(encoding="utf-8")
    readme = PACKAGE_README.read_text(encoding="utf-8")
    model_docs = (MODULE_DOCS / "MODEL_DOCUMENTATION.md").read_text(encoding="utf-8")

    assert "docs/regulatory_sources.yml" in traceability
    assert "regulatory_sources.yml" in assumptions
    assert "docs/REGULATORY_TRACEABILITY.md" in readme
    assert "Package regulatory traceability" in model_docs
