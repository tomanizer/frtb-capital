"""Tests for GitHub Actions changed-path classification."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_classifier() -> ModuleType:
    if "classify_changed_paths" in sys.modules:
        return sys.modules["classify_changed_paths"]
    script_path = REPO_ROOT / "scripts" / "ci" / "classify_changed_paths.py"
    spec = importlib.util.spec_from_file_location("classify_changed_paths", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["classify_changed_paths"] = module
    spec.loader.exec_module(module)
    return module


def classify(paths: set[str], event_name: str = "pull_request") -> dict[str, bool]:
    return load_classifier()._classify(paths, event_name)


def test_docs_only_pr_does_not_force_heavy_ci() -> None:
    outputs = classify({"docs/AGENT_WORKTREE_POLICY.md"})

    assert outputs == {
        "full": False,
        "docs": True,
        "code": False,
        "test": False,
        "dependency": False,
        "notebooks": False,
        "examples": False,
        "workflow": False,
    }


def test_dependency_change_runs_code_and_dependency_checks() -> None:
    outputs = classify({"uv.lock"})

    assert outputs["code"] is True
    assert outputs["test"] is True
    assert outputs["dependency"] is True
    assert outputs["docs"] is False
    assert outputs["notebooks"] is True
    assert outputs["examples"] is True


def test_workflow_change_runs_full_ci_surface() -> None:
    outputs = classify({".github/workflows/ci.yml"})

    assert outputs == {
        "full": False,
        "docs": True,
        "code": True,
        "test": True,
        "dependency": True,
        "notebooks": True,
        "examples": True,
        "workflow": True,
    }


def test_push_runs_full_ci_surface() -> None:
    outputs = classify({"README.md"}, event_name="push")

    assert outputs == {
        "full": True,
        "docs": True,
        "code": True,
        "test": True,
        "dependency": True,
        "notebooks": True,
        "examples": True,
        "workflow": False,
    }


def test_agent_instruction_pr_skips_runtime_tests() -> None:
    outputs = classify({".github/copilot-instructions.md"})

    assert outputs["code"] is True
    assert outputs["docs"] is True
    assert outputs["test"] is False


def test_root_test_fixture_pr_runs_runtime_tests() -> None:
    outputs = classify({"tests/fixtures/example.json"})

    assert outputs["test"] is True


def test_package_example_python_pr_runs_runtime_tests() -> None:
    outputs = classify({"packages/frtb-sbm/examples/sbm_notebook_data.py"})

    assert outputs["code"] is True
    assert outputs["test"] is True


def test_package_script_python_pr_runs_runtime_tests() -> None:
    outputs = classify({"packages/frtb-drc/scripts/generate_fixture.py"})

    assert outputs["code"] is True
    assert outputs["test"] is True


def test_diff_name_only_falls_back_when_shallow_checkout_lacks_merge_base(
    monkeypatch,
) -> None:
    classifier = load_classifier()
    calls: list[list[str]] = []

    def fake_git_lines(args: list[str]) -> list[str]:
        calls.append(args)
        if args == ["diff", "--name-only", "base-sha...HEAD"]:
            raise subprocess.CalledProcessError(128, ["git", *args])
        return ["packages/frtb-sbm/src/frtb_sbm/capital.py"]

    monkeypatch.setattr(classifier, "_git_lines", fake_git_lines)

    assert classifier._diff_name_only("base-sha") == ["packages/frtb-sbm/src/frtb_sbm/capital.py"]
    assert calls == [
        ["diff", "--name-only", "base-sha...HEAD"],
        ["diff", "--name-only", "base-sha", "HEAD"],
    ]
