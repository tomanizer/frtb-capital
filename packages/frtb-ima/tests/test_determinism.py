"""Determinism checks for the committed capital-run fixture."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from tests.fixture_loader import load_capital_run_fixture
from tests.test_capital_run_fixture import FIXTURE_ROOT, _run_fixture_workflow

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
    digest = capital_run_v1_determinism_hash(_run_fixture_workflow(fixture))
    expected = registry_path.read_text(encoding="utf-8").strip()

    assert digest == expected


def capital_run_v1_determinism_hash(outputs: object) -> str:
    """Return the SHA-256 hash for canonical serialised fixture outputs."""
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
    return hashlib.sha256(f"{serialized}\n".encode()).hexdigest()
