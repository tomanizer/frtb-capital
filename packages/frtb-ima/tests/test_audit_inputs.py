"""Tests for canonical input hashing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.capital_run_fixture import input_hash_for_capital_run_fixture
from tests.capital_run_fixture_workflow import FIXTURE_ROOT
from tests.fixture_loader import load_capital_run_fixture


def test_compute_inputs_hash_is_stable_for_capital_run_fixture() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)

    first = input_hash_for_capital_run_fixture(fixture)
    second = input_hash_for_capital_run_fixture(fixture)

    assert first == second
    assert len(first) == 64


def test_compute_inputs_hash_changes_when_fixture_input_changes() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)
    changed_values = fixture.scenario_cube.values.copy()
    changed_values[0, 0, 0] += 0.01
    changed_cube = replace(fixture.scenario_cube, values=changed_values)
    changed_fixture = replace(fixture, scenario_cube=changed_cube)

    assert input_hash_for_capital_run_fixture(fixture) != input_hash_for_capital_run_fixture(
        changed_fixture
    )


def test_compute_inputs_hash_rejects_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        compute_inputs_hash(values=np.array([1.0, float("nan")]))


def test_compute_inputs_hash_canonicalizes_supported_scalar_and_container_types() -> None:
    class Label(StrEnum):
        PRIMARY = "PRIMARY"

    @dataclass(frozen=True)
    class Payload:
        label: Label
        as_of: date

    first = compute_inputs_hash(
        payload=Payload(Label.PRIMARY, date(2026, 5, 28)),
        mapping=MappingProxyType({"b": 2, "a": 1}),
        unordered={"z", "a"},
        timestamp=datetime(2026, 5, 28, 12, 0, 0),
        path=Path("synthetic/input.csv"),
        bytes_value=b"synthetic bytes",
        numpy_scalar=np.float64(1.25),
        bool_value=True,
        none_value=None,
    )
    second = compute_inputs_hash(
        unordered={"a", "z"},
        mapping={"a": 1, "b": 2},
        payload=Payload(Label.PRIMARY, date(2026, 5, 28)),
        timestamp=datetime(2026, 5, 28, 12, 0, 0),
        path=Path("synthetic/input.csv"),
        bytes_value=b"synthetic bytes",
        numpy_scalar=np.float64(1.25),
        bool_value=True,
        none_value=None,
    )

    assert first == second


def test_compute_inputs_hash_handles_datetime64_and_raw_byte_arrays() -> None:
    digest = compute_inputs_hash(
        dates=np.array(["2026-05-28"], dtype="datetime64[D]"),
        complex_values=np.array([1 + 2j, 3 + 4j], dtype=np.complex128),
    )

    assert len(digest) == 64


def test_compute_inputs_hash_rejects_unsupported_values() -> None:
    with pytest.raises(TypeError, match="object-dtype"):
        compute_inputs_hash(values=np.array([object()], dtype=object))

    with pytest.raises(ValueError, match="non-finite floats"):
        compute_inputs_hash(value=float("inf"))

    with pytest.raises(TypeError, match="unsupported"):
        compute_inputs_hash(value=object())
