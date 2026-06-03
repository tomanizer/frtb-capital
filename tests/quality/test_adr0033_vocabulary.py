from __future__ import annotations

from pathlib import Path

from scripts.ci import check_adr0033_vocabulary as guard


def test_public_handoff_symbol_guard_reports_old_aliases(tmp_path: Path) -> None:
    source_root = tmp_path / "packages" / "pkg" / "src" / "pkg"
    source_root.mkdir(parents=True)
    (source_root / "module.py").write_text(
        """
RRAO_HANDOFF_COLUMN_SPECS = ()

def build_rrao_batch_from_handoff(value):
    return value

def build_rrao_batch_from_arrow(value):
    return value
""",
        encoding="utf-8",
    )

    findings = guard.public_handoff_symbol_findings(tmp_path / "packages")

    assert [finding.symbol for finding in findings] == [
        "RRAO_HANDOFF_COLUMN_SPECS",
        "build_rrao_batch_from_handoff",
    ]


def test_public_handoff_symbol_guard_reports_new_public_names(tmp_path: Path) -> None:
    source_root = tmp_path / "packages" / "pkg" / "src" / "pkg"
    source_root.mkdir(parents=True)
    source = source_root / "module.py"
    source.write_text(
        """
def calculate_new_handoff_contract():
    return None
""",
        encoding="utf-8",
    )

    findings = guard.public_handoff_symbol_findings(tmp_path / "packages")

    assert len(findings) == 1
    assert findings[0].path == source
    assert findings[0].symbol == "calculate_new_handoff_contract"


def test_duplicate_adr_prefixes_are_reported(tmp_path: Path) -> None:
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    first = decisions / "0001-first.md"
    second = decisions / "0001-second.md"
    first.write_text("# First\n", encoding="utf-8")
    second.write_text("# Second\n", encoding="utf-8")

    assert guard.duplicate_adr_prefixes(decisions) == {"0001": (first, second)}
