"""Tests for GitHub Actions changed-path classification."""

from __future__ import annotations

import importlib.util
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
        "dependency": False,
        "notebooks": False,
        "examples": False,
        "workflow": False,
    }


def test_dependency_change_runs_code_and_dependency_checks() -> None:
    outputs = classify({"uv.lock"})

    assert outputs["code"] is True
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
        "dependency": True,
        "notebooks": True,
        "examples": True,
        "workflow": False,
    }
