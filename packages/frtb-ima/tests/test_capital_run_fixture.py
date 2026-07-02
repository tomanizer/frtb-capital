"""Integration regression test for the committed capital-run v1 fixture."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy.testing as npt
import pytest

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.lha_builder import imcc_nested_lh_vectors_from_cube
from tests.capital_run_fixture_workflow import (
    FIXTURE_ROOT,
    run_capital_run_fixture_workflow,
)
from tests.fixture_loader import _verify_manifest_checksums, load_capital_run_fixture


def test_capital_run_v1_happy_path_matches_golden_outputs() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)

    actual = run_capital_run_fixture_workflow(fixture)
    expected = fixture.expected_outputs

    for name, golden in expected["scalars"].items():
        _assert_golden_scalar(name, actual["scalars"][name], golden)

    assert actual["classifications"] == expected["classifications"]
    assert actual["nmrf_methods"] == expected["nmrf_methods"]
    assert actual["selected_stress_periods"] == expected["selected_stress_periods"]
    assert actual["reconciliation"] == expected["reconciliation"]
    assert actual["pla"] == expected["pla"]
    assert actual["backtesting"] == expected["backtesting"]
    assert actual["capital"] == expected["capital"]


def test_capital_run_v1_manifest_declares_sign_conventions() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)

    conventions = fixture.manifest["sign_conventions"]
    assert conventions["scenario_cube.npz"]["cube"] == "positive_loss"
    assert conventions["nmrf_artifacts.npz"]["*_losses"] == "positive_loss"
    assert conventions["pla_bt_vectors.npz"]["apl"] == "positive_profit"
    assert conventions["pla_bt_vectors.npz"]["var_99"] == "positive_magnitude"
    assert not fixture.scenario_cube.values.flags.writeable
    assert not fixture.nmrf_artifacts["HY_CREDIT_SPD_losses"].flags.writeable
    assert not fixture.pla_bt_vectors["apl"].flags.writeable


def test_capital_run_v1_preserves_fixture_artifact_provenance() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)

    assert fixture.scenario_cube.artifact_id == "artifact:ima:capital_run_v1:scenario_cube"
    assert fixture.scenario_cube.scenario_set_id == "scenario-set:ima:capital_run_v1:current"
    assert fixture.scenario_cube.scenario_vector_ids[0] == (
        "scenario-vector:ima:capital_run_v1:current:current-00000"
    )
    assert fixture.rfet_evidence["COMM_BASIS_RF"].observation_time_series_id == (
        "ts:ima:capital_run_v1:rfet:COMM_BASIS_RF"
    )
    assert fixture.rfet_evidence["COMM_BASIS_RF"].observations[0].source_row_id == (
        "rfet_observations.csv:00000"
    )

    nested_vectors = imcc_nested_lh_vectors_from_cube(
        fixture.scenario_cube,
        fixture.risk_factors,
    )
    lh10_component = nested_vectors.all_risk_class_vectors[LiquidityHorizon.LH10]
    assert lh10_component.source_scenario_cube_id == fixture.scenario_cube.artifact_id
    assert lh10_component.scenario_vector_ids == fixture.scenario_cube.scenario_vector_ids


def test_fixture_manifest_checksum_mismatch_has_clear_message(tmp_path: Path) -> None:
    data_file = tmp_path / "data.txt"
    data_file.write_text("fixture payload")
    manifest = {"files": {"data.txt": {"sha256": "0" * 64}}}

    with pytest.raises(AssertionError, match=r"manifest checksum mismatch for data\.txt"):
        _verify_manifest_checksums(tmp_path, manifest)


def test_fixture_manifest_rejects_paths_outside_fixture_root(tmp_path: Path) -> None:
    manifest = {"files": {"../outside.txt": {"sha256": "0" * 64}}}

    with pytest.raises(AssertionError, match="escapes fixture root"):
        _verify_manifest_checksums(tmp_path, manifest)


def _assert_golden_scalar(
    name: str,
    actual: object,
    expected: Mapping[str, object],
) -> None:
    assert "value" in expected, name
    npt.assert_allclose(
        float(actual),
        float(expected["value"]),
        rtol=float(expected.get("rtol", 1e-9)),
        atol=float(expected.get("atol", 1e-9)),
        err_msg=name,
    )
