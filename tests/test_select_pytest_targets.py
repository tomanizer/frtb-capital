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
    assert select({"packages/frtb-sbm/src/frtb_sbm/capital.py"}) == ("packages/frtb-sbm/tests",)


def test_common_runtime_change_selects_full_suite() -> None:
    assert select({"packages/frtb-common/src/frtb_common/handoff.py"}) == ("packages", "tests")


def test_ci_script_change_selects_tooling_tests() -> None:
    assert select({"scripts/ci/check_code_drift.py"}) == (
        "packages/frtb-common/tests",
        "tests",
    )


def test_docs_change_selects_no_pytest_targets() -> None:
    assert select({"docs/AGENT_WORKTREE_POLICY.md"}) == ()


def test_root_test_fixture_change_selects_root_tests() -> None:
    assert select({"tests/fixtures/example.json"}) == ("tests",)
