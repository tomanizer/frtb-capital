from __future__ import annotations

from pathlib import Path

from scripts.ci import check_docs_staleness as staleness


def test_docs_staleness_flags_current_scaffold_language(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs" / "modules"
    docs.mkdir(parents=True)
    current_doc = docs / "README.md"
    current_doc.write_text(
        "The following packages are importable scaffolds with no model validation pack yet.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(staleness, "ROOT", repo_root)

    findings = staleness.scan_current_docs()

    assert {finding.rule for finding in findings} == {
        "stale-scaffold-status",
        "no-validation-pack-yet",
    }


def test_docs_staleness_allows_fail_closed_placeholder_context(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "packages" / "frtb-sbm" / "docs"
    docs.mkdir(parents=True)
    current_doc = docs / "REGULATORY_TRACEABILITY.md"
    current_doc.write_text(
        "Placeholder source mapping is retained only for unsupported paths that fail closed.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(staleness, "ROOT", repo_root)

    assert staleness.scan_current_docs() == []


def test_docs_staleness_flags_generic_prototype_wording(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs" / "quality"
    docs.mkdir(parents=True)
    current_doc = docs / "PACKAGE_STATUS.md"
    current_doc.write_text(
        "Outputs from this suite are prototype model-validation evidence.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(staleness, "ROOT", repo_root)

    findings = staleness.scan_current_docs()

    assert [finding.rule for finding in findings] == ["generic-prototype-wording"]


def test_docs_staleness_scans_top_level_docs_readme(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs"
    docs.mkdir(parents=True)
    current_doc = docs / "README.md"
    current_doc.write_text(
        "This validation-pack page will add future docs.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(staleness, "ROOT", repo_root)

    findings = staleness.scan_current_docs()

    assert [finding.rule for finding in findings] == ["future-docs-needed"]


def test_docs_staleness_future_docs_rule_is_order_independent(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs"
    docs.mkdir(parents=True)
    current_doc = docs / "VALIDATION_PACK.md"
    current_doc.write_text(
        "We need to add future docs for this package.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(staleness, "ROOT", repo_root)

    findings = staleness.scan_current_docs()

    assert [finding.rule for finding in findings] == ["future-docs-needed"]


def test_docs_staleness_flags_plural_placeholder_wording(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs" / "modules"
    docs.mkdir(parents=True)
    current_doc = docs / "README.md"
    current_doc.write_text(
        "These placeholders still describe current package status.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(staleness, "ROOT", repo_root)

    findings = staleness.scan_current_docs()

    assert [finding.rule for finding in findings] == ["placeholder-without-status"]
