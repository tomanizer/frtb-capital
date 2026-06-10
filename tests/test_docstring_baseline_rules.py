from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.ci.check_docstring_baseline import (
    DEFAULT_BASELINE,
    DEFAULT_SECTION_BASELINE,
    HARD_RULES,
    REPORT_ONLY_RULES,
    compare_to_baseline,
    load_baseline,
)
from scripts.ci.docstring_inventory import DocstringFinding

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_committed_docstring_baselines_are_valid() -> None:
    load_baseline(REPO_ROOT / DEFAULT_BASELINE)
    load_baseline(REPO_ROOT / DEFAULT_SECTION_BASELINE)


def test_compare_to_baseline_accepts_section_supplement() -> None:
    module_finding = _finding("MISSING_MODULE_DOCSTRING", "module", "frtb_example.module")
    section_finding = _finding("MISSING_PARAMETERS_SECTION", "function", "calculate")
    report_only_finding = _finding("TRIVIAL_DOCSTRING", "function", "helper")

    comparison = compare_to_baseline(
        [module_finding, section_finding, report_only_finding],
        [_baseline(module_finding), _baseline(section_finding)],
    )

    assert comparison.new_findings == ()
    assert comparison.stale_findings == ()


def _finding(rule: str, object_type: str, object_name: str) -> DocstringFinding:
    return DocstringFinding(
        package="frtb-example",
        path="packages/frtb-example/src/frtb_example/module.py",
        rule=rule,
        object_type=object_type,
        object_name=object_name,
        line=1,
        message=f"{rule} message",
    )


def _baseline(*findings: DocstringFinding) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "description": "test baseline",
        "paths": ["packages"],
        "metrics": {
            "total_findings": len(findings),
            "packages_with_findings": 1 if findings else 0,
            "findings_by_rule": {finding.rule: 1 for finding in findings},
        },
        "packages": {
            "frtb-example": {
                "finding_count": len(findings),
                "findings": [
                    {
                        "package": finding.package,
                        "path": finding.path,
                        "line": finding.line,
                        "rule": finding.rule,
                        "object_type": finding.object_type,
                        "object_name": finding.object_name,
                        "message": finding.message,
                    }
                    for finding in findings
                ],
            }
        },
    }
