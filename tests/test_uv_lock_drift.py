from __future__ import annotations

from scripts.ci.check_uv_lock_drift import _dependency_spec_snapshot


def test_dependency_spec_snapshot_includes_optional_dependencies() -> None:
    before = b"""
[project]
dependencies = ["frtb-common"]

[project.optional-dependencies]
api = ["duckdb>=1.4,<2"]
"""
    after = b"""
[project]
dependencies = ["frtb-common"]

[project.optional-dependencies]
api = ["duckdb>=1.4,<2"]
cli = ["duckdb>=1.4,<2"]
"""

    assert _dependency_spec_snapshot(before) != _dependency_spec_snapshot(after)
