"""Tests for canonical input hashing."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from frtb_ima.audit_inputs import compute_inputs_hash
from tests.capital_run_fixture_workflow import FIXTURE_ROOT
from tests.fixture_loader import load_capital_run_fixture


def test_compute_inputs_hash_is_stable_for_capital_run_fixture() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)

    first = _fixture_inputs_hash(fixture)
    second = _fixture_inputs_hash(fixture)

    assert first == second
    assert len(first) == 64


def test_compute_inputs_hash_changes_when_fixture_input_changes() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)
    changed_values = fixture.scenario_cube.values.copy()
    changed_values[0, 0, 0] += 0.01
    changed_cube = replace(fixture.scenario_cube, values=changed_values)
    changed_fixture = replace(fixture, scenario_cube=changed_cube)

    assert _fixture_inputs_hash(fixture) != _fixture_inputs_hash(changed_fixture)


def test_compute_inputs_hash_rejects_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        compute_inputs_hash(values=np.array([1.0, float("nan")]))


def _fixture_inputs_hash(fixture: object) -> str:
    return compute_inputs_hash(
        params=fixture.params,
        risk_factors=fixture.risk_factors,
        rfet_evidence=fixture.rfet_evidence,
        scenario_cube=fixture.scenario_cube,
        stress_histories=fixture.stress_histories,
        nmrf_evidence=fixture.nmrf_evidence,
        nmrf_artifacts=fixture.nmrf_artifacts,
        pla_bt_vectors=fixture.pla_bt_vectors,
    )
