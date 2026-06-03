from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.ci.check_test_value import (
    Thresholds,
    build_report,
    collect_test_value_errors,
)


def test_test_value_guard_detects_untracked_test_without_assertion(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_shallow.py").write_text(
        """
def test_constructs_object() -> None:
    value = {"capital": 1}
    dict(value)
""".lstrip(),
        encoding="utf-8",
    )

    report = build_report(tmp_path, "HEAD", ["tests"], Thresholds())
    errors = collect_test_value_errors(report)

    assert any("has no value assertion" in error for error in errors)


def test_test_value_guard_allows_pytest_raises(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_error.py").write_text(
        """
import pytest


def test_rejects_bad_value() -> None:
    with pytest.raises(ValueError):
        raise ValueError("bad")
""".lstrip(),
        encoding="utf-8",
    )

    report = build_report(tmp_path, "HEAD", ["tests"], Thresholds())
    errors = collect_test_value_errors(report)

    assert errors == []


def test_test_value_guard_detects_duplicate_changed_test_bodies(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_duplicate.py").write_text(
        """
def test_first() -> None:
    value = 1 + 1
    assert value == 2


def test_second() -> None:
    value = 1 + 1
    assert value == 2
""".lstrip(),
        encoding="utf-8",
    )

    report = build_report(tmp_path, "HEAD", ["tests"], Thresholds())
    errors = collect_test_value_errors(report)

    assert any("duplicate changed test body" in error for error in errors)


def test_test_value_guard_detects_large_fixture_growth(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "payload.json").write_text("x" * 12, encoding="utf-8")

    report = build_report(
        tmp_path,
        "HEAD",
        ["tests"],
        Thresholds(fixture_file_bytes=10),
    )
    errors = collect_test_value_errors(report)

    assert any("fixture grew" in error for error in errors)


def _init_repo(path: Path) -> None:
    _git(path, "init")
    _git(path, "config", "user.email", "agent@example.com")
    _git(path, "config", "user.name", "Agent")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "base")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=cwd, check=True, capture_output=True, text=True)
