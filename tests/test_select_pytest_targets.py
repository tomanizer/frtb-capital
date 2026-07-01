"""Tests for changed-path pytest target selection."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_selector() -> ModuleType:
    if "select_pytest_targets" in sys.modules:
        return sys.modules["select_pytest_targets"]
    script_dir = REPO_ROOT / "scripts" / "ci"
    sys.path.insert(0, str(script_dir))
    import select_pytest_targets

    return select_pytest_targets


def select(paths: set[str]) -> tuple[str, ...]:
    return load_selector().select_targets(paths)


def test_single_package_runtime_change_selects_package_tests() -> None:
    assert select({"packages/frtb-sbm/src/frtb_sbm/capital.py"}) == ("packages", "tests")


def test_common_runtime_change_selects_full_suite() -> None:
    assert select({"packages/frtb-common/src/frtb_common/handoff.py"}) == ("packages", "tests")


def test_ci_script_change_selects_tooling_tests() -> None:
    assert select({"scripts/ci/check_code_drift.py"}) == (
        "tests",
        "packages/frtb-common/tests",
    )


def test_docs_change_selects_no_pytest_targets() -> None:
    assert select({"docs/AGENT_WORKTREE_POLICY.md"}) == ()


def test_root_test_fixture_change_selects_root_tests() -> None:
    assert select({"tests/fixtures/example.json"}) == ("tests",)


def test_package_example_python_change_selects_package_tests() -> None:
    assert select({"packages/frtb-sbm/examples/sbm_notebook_data.py"}) == ("packages", "tests")


def test_package_script_python_change_selects_package_tests() -> None:
    assert select({"packages/frtb-drc/scripts/generate_fixture.py"}) == ("packages", "tests")


def test_common_package_support_python_change_selects_full_suite() -> None:
    assert select({"packages/frtb-common/scripts/generate_fixture.py"}) == (
        "packages",
        "tests",
    )


def test_local_changed_paths_fail_closed_to_full_suite(monkeypatch) -> None:
    selector = load_selector()

    def fake_git_lines(args: list[str], *, check: bool = False) -> list[str]:
        if args == ["merge-base", "missing-base", "HEAD"]:
            return []
        if args == ["diff", "--name-only", "missing-base", "HEAD"] and check:
            raise selector.subprocess.CalledProcessError(128, ["git", *args])
        return []

    monkeypatch.setattr(selector, "_git_lines", fake_git_lines)

    assert selector._local_changed_paths("missing-base") is None


def test_main_prints_full_suite_when_local_paths_are_unknown(monkeypatch, capsys) -> None:
    selector = load_selector()

    monkeypatch.setattr(selector, "_changed_paths", lambda base_ref: None)

    assert selector.main(["--base", "missing-base"]) == 0
    assert capsys.readouterr().out.strip() == "packages tests"
