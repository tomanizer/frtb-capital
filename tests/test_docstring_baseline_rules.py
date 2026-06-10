from __future__ import annotations

from pathlib import Path

from scripts.ci.check_docstring_baseline import HARD_RULES, REPORT_ONLY_RULES, load_baseline


def test_docstring_baseline_hard_rules_include_stable_section_rules() -> None:
    assert HARD_RULES == frozenset(
        {
            "MISSING_MODULE_DOCSTRING",
            "MISSING_PUBLIC_DOCSTRING",
            "MISSING_PARAMETERS_SECTION",
            "MISSING_RETURNS_SECTION",
        }
    )
    assert REPORT_ONLY_RULES == frozenset({"TRIVIAL_DOCSTRING"})
    assert HARD_RULES.isdisjoint(REPORT_ONLY_RULES)


def test_committed_docstring_baseline_tracks_promoted_section_rules() -> None:
    baseline = load_baseline(Path("docs/quality/docstrings/baseline.json"))
    baseline_rules = {
        finding["rule"]
        for package_payload in baseline["packages"].values()
        for finding in package_payload["findings"]
        if finding["rule"] in HARD_RULES
    }

    assert "MISSING_PARAMETERS_SECTION" in baseline_rules
    assert "MISSING_RETURNS_SECTION" in baseline_rules
