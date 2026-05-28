"""Determinism checks for the committed capital-run fixture."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from tests.capital_run_fixture_workflow import (
    FIXTURE_ROOT,
    run_capital_run_fixture_workflow,
)
from tests.fixture_loader import load_capital_run_fixture

DETERMINISM_ROOT = Path(__file__).resolve().parent / "fixtures" / "determinism"
SUPPORTED_CI_PYTHON_MINORS = ("3.11", "3.12", "3.13")
DETERMINISM_SCHEMA_VERSION = "capital_run_v1_determinism_v1"


def test_determinism_registry_covers_ci_python_matrix() -> None:
    """Ensure every CI Python minor has a committed hash expectation."""
    expected_files = {f"{minor}.sha256" for minor in SUPPORTED_CI_PYTHON_MINORS}
    actual_files = {path.name for path in DETERMINISM_ROOT.glob("*.sha256")}

    assert actual_files == expected_files


def test_capital_run_v1_hash_matches_python_registry() -> None:
    """Run the full fixture and compare the canonical output hash for this Python minor."""
    python_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    registry_path = DETERMINISM_ROOT / f"{python_minor}.sha256"
    if not registry_path.exists():
        pytest.skip(f"no committed determinism expectation for Python {python_minor}")

    fixture = load_capital_run_fixture(FIXTURE_ROOT)
    digest = capital_run_v1_determinism_hash(run_capital_run_fixture_workflow(fixture))
    expected = registry_path.read_text(encoding="utf-8").strip()

    assert digest == expected


def capital_run_v1_determinism_hash(outputs: object) -> str:
    """Return the SHA-256 hash for bit-identical serialised fixture outputs.

    The test intentionally hashes raw numeric outputs rather than rounded values:
    its audit purpose is to detect even tiny fixture-output drift within the
    supported CI Python matrix. Platform and BLAS limits are documented with the
    determinism guarantee.
    """
    payload = {
        "schema_version": DETERMINISM_SCHEMA_VERSION,
        "fixture": "capital_run_v1",
        "outputs": outputs,
    }
    serialized = json.dumps(
        payload,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    raw_payload = bytes(f"{serialized}\n", "utf-8")
    return hashlib.sha256(raw_payload).hexdigest()
