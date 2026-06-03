from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.ci.check_code_drift import (
    Thresholds,
    build_changed_report,
    build_report,
    changed_code_errors,
    compare_to_baseline,
    main,
)


def test_code_drift_guard_detects_new_duplicate_function_group(tmp_path: Path) -> None:
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "one.py").write_text(
        """
def unique(value: int) -> int:
    total = value + 1
    total *= 2
    total -= 3
    total += value
    return total
""".lstrip(),
        encoding="utf-8",
    )
    thresholds = Thresholds(duplicate_function_lines=5)
    baseline = build_report(tmp_path, ["packages"], thresholds)

    (source / "two.py").write_text(
        """
def duplicate(value: int) -> int:
    total = value + 1
    total *= 2
    total -= 3
    total += value
    return total
""".lstrip(),
        encoding="utf-8",
    )
    report = build_report(tmp_path, ["packages"], thresholds)

    errors = compare_to_baseline(report, baseline, thresholds)

    assert any("duplicate_function_groups grew" in error for error in errors)


def test_code_drift_guard_detects_new_oversized_file(tmp_path: Path) -> None:
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "small.py").write_text("VALUE = 1\n", encoding="utf-8")
    thresholds = Thresholds(source_file_lines=3)
    baseline = build_report(tmp_path, ["packages"], thresholds)

    (source / "large.py").write_text(
        "VALUE = 1\nVALUE = 2\nVALUE = 3\nVALUE = 4\n", encoding="utf-8"
    )
    report = build_report(tmp_path, ["packages"], thresholds)

    errors = compare_to_baseline(report, baseline, thresholds)

    assert any("is a new oversized file" in error for error in errors)


def test_code_drift_guard_allows_loc_growth_inside_budget(tmp_path: Path) -> None:
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    thresholds = Thresholds(source_python_loc_growth=2, total_python_loc_growth=2)
    baseline = build_report(tmp_path, ["packages"], thresholds)

    (source / "module.py").write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
    report = build_report(tmp_path, ["packages"], thresholds)

    errors = compare_to_baseline(report, baseline, thresholds)

    assert errors == []


def test_code_drift_large_function_key_is_line_independent(tmp_path: Path) -> None:
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "module.py").write_text(
        """
def large() -> int:
    value = 1
    value += 1
    value += 1
    value += 1
    value += 1
    return value
""".lstrip(),
        encoding="utf-8",
    )

    report = build_report(tmp_path, ["packages"], Thresholds(function_lines=5))

    assert "packages/demo/src/demo/module.py:large" in report["large_functions"]


def test_code_drift_main_reports_invalid_baseline_json(tmp_path: Path, capsys) -> None:
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{not-json", encoding="utf-8")

    exit_code = main(["--root", str(tmp_path), "--baseline", str(baseline), "--quiet"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "failed to parse code drift baseline" in captured.err


def test_changed_code_guard_allows_untracked_trivial_wrapper() -> None:
    report = {
        "schema_version": 1,
        "files": {},
        "changed_functions": {
            "packages/demo/src/demo/wrappers.py:wrapper": {
                "lines": 2,
                "base_lines": 0,
                "is_new": True,
            }
        },
        "large_functions": {},
    }

    errors = changed_code_errors(report, Thresholds())

    assert errors == []


def test_changed_code_guard_detects_untracked_file_growth(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "agent@example.com")
    _git(tmp_path, "config", "user.name", "Agent")
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "base.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")

    (source / "growth.py").write_text("VALUE = 1\nOTHER = 2\nTHIRD = 3\n", encoding="utf-8")

    thresholds = Thresholds(changed_source_loc_growth=1)
    report = build_changed_report(tmp_path, "HEAD", ["packages"], thresholds)
    errors = changed_code_errors(report, thresholds)

    assert any("growth.py grew by 3 logical LOC" in error for error in errors)


def test_changed_code_guard_detects_large_function() -> None:
    thresholds = Thresholds(function_lines=5)
    report = {
        "schema_version": 1,
        "files": {},
        "large_functions": {
            "packages/demo/src/demo/module.py:large": {
                "lines": 6,
                "base_lines": 0,
                "is_new": True,
            }
        },
    }

    errors = changed_code_errors(report, thresholds)

    assert any("changed large function" in error for error in errors)


def test_changed_code_guard_detects_file_growth_over_budget() -> None:
    thresholds = Thresholds(changed_source_loc_growth=2)
    report = {
        "schema_version": 1,
        "files": {
            "packages/demo/src/demo/module.py": {
                "loc_delta": 3,
                "growth_budget": 2,
            }
        },
        "large_functions": {},
    }

    errors = changed_code_errors(report, thresholds)

    assert errors == ["packages/demo/src/demo/module.py grew by 3 logical LOC (budget +2)"]


def test_changed_code_guard_uses_first_parent_when_base_ref_is_missing(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "agent@example.com")
    _git(tmp_path, "config", "user.name", "Agent")
    source = tmp_path / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    (source / "module.py").write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "head")

    report = build_changed_report(tmp_path, "origin/main", ["packages"], Thresholds())

    assert report["merge_base"]
    assert report["metrics"]["changed_python_files"] == 1


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=cwd, check=True, capture_output=True, text=True)
