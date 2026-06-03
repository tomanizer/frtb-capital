"""PRA UK CRR IMA profile runtime and fixture coverage."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy.testing as npt

from frtb_ima.capital_run_fixture import load_capital_run_pra_fixture
from frtb_ima.regimes import RegulatoryRegime, get_policy
from frtb_ima.rfet_evidence import assess_rfet_evidence
from tests.capital_run_fixture_workflow import run_capital_run_fixture_workflow
from tests.fixture_loader import load_capital_run_fixture

PRA_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ima_pra"
V1_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "capital_run_v1"


def test_pra_policy_exposes_uk_citations_and_partial_runtime() -> None:
    policy = get_policy(RegulatoryRegime.PRA_UK_CRR)
    assert policy.regime is RegulatoryRegime.PRA_UK_CRR
    assert policy.unsupported_feature("pra_uk_crr_capital_runtime") is None
    assert "UK CRR Article 325be" in policy.cited_by["rfet_short_lh_threshold"]
    assert policy.unsupported_feature("pra_specific_calibration") is not None


def test_pra_rfet_assessment_runs_without_capital_runtime_block() -> None:
    fixture = load_capital_run_fixture(V1_FIXTURE_ROOT)
    risk_factor = fixture.risk_factors[0]
    assessment = assess_rfet_evidence(
        risk_factor,
        fixture.rfet_evidence[risk_factor.name],
        get_policy(RegulatoryRegime.PRA_UK_CRR),
    )
    assert assessment.risk_factor_name == risk_factor.name


def test_ima_pra_fixture_workflow_matches_expected_outputs() -> None:
    fixture = load_capital_run_pra_fixture()
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


def _assert_golden_scalar(
    name: str,
    actual: object,
    expected: Mapping[str, object],
) -> None:
    npt.assert_allclose(
        float(actual),
        float(expected["value"]),
        rtol=float(expected.get("rtol", 1e-9)),
        atol=float(expected.get("atol", 1e-9)),
        err_msg=name,
    )


def test_load_capital_run_pra_fixture_matches_v1_inputs_except_regime() -> None:
    pra = load_capital_run_pra_fixture()
    v1 = load_capital_run_fixture(V1_FIXTURE_ROOT)
    assert pra.params["regime"] == "PRA_UK_CRR"
    assert pra.risk_factors == v1.risk_factors
    assert pra.scenario_cube.values.shape == v1.scenario_cube.values.shape
