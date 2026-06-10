from __future__ import annotations

from scripts.ci.check_docstring_baseline import (
    DEFAULT_BASELINE,
    DEFAULT_SECTION_BASELINE,
    HARD_RULES,
    REPORT_ONLY_RULES,
    load_baseline,
)


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


def test_committed_docstring_baselines_track_promoted_section_rules() -> None:
    baselines = [load_baseline(DEFAULT_BASELINE), load_baseline(DEFAULT_SECTION_BASELINE)]
    baseline_rules = {
        finding["rule"]
        for baseline in baselines
        for package_payload in baseline["packages"].values()
        for finding in package_payload["findings"]
        if finding["rule"] in HARD_RULES
    }

    assert "MISSING_PARAMETERS_SECTION" in baseline_rules
    assert "MISSING_RETURNS_SECTION" in baseline_rules


def test_section_baseline_is_focused_on_promoted_section_rules() -> None:
    section_baseline = load_baseline(DEFAULT_SECTION_BASELINE)
    section_rules = {
        finding["rule"]
        for package_payload in section_baseline["packages"].values()
        for finding in package_payload["findings"]
    }

    assert section_rules == {"MISSING_PARAMETERS_SECTION", "MISSING_RETURNS_SECTION"}
    assert section_baseline["metrics"]["total_findings"] == 38
