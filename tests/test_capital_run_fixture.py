"""Integration regression test for the committed capital-run v1 fixture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import numpy.testing as npt
import pytest

from frtb_ima.backtesting import trading_desk_backtest_trace_for_policy
from frtb_ima.capital import models_based_capital, supervisory_multiplier_for_policy
from frtb_ima.data_contracts import ScenarioCube
from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.imcc import imcc_breakdown_for_policy
from frtb_ima.lha_builder import imcc_nested_lh_vectors_from_cube
from frtb_ima.nmrf import (
    NMRFStressArtifact,
    route_nmrf_classifications_for_capital,
)
from frtb_ima.nmrf_method_selection import (
    NMRFMethodEvidence,
    assess_direct_loss_robustness,
    select_nmrf_methods,
    selection_input_from_method_evidence,
)
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFFullRevaluationSpec,
    NMRFShockDirection,
    NMRFValuationSpec,
    build_nmrf_valuation_specs,
)
from frtb_ima.nmrf_valuation_run import (
    build_nmrf_valuation_run_request,
    calculate_nmrf_capital_from_valuation_run,
    complete_nmrf_valuation_run,
)
from frtb_ima.pla import pla_assessment_for_policy_with_diagnostics
from frtb_ima.regimes import RegulatoryPolicy, RegulatoryRegime, get_policy
from frtb_ima.rfet_evidence import assess_rfet_evidence
from frtb_ima.stress_periods import (
    select_stress_periods_for_policy,
    stress_period_specs_for_nmrf,
    validate_selected_stress_periods,
)
from tests.fixture_loader import (
    CapitalRunFixture,
    _verify_manifest_checksums,
    load_capital_run_fixture,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "capital_run_v1"


def test_capital_run_v1_happy_path_matches_golden_outputs() -> None:
    fixture = load_capital_run_fixture(FIXTURE_ROOT)

    actual = _run_fixture_workflow(fixture)
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


def _run_fixture_workflow(fixture: CapitalRunFixture) -> dict[str, object]:
    policy = get_policy(RegulatoryRegime(str(fixture.params["regime"])))
    as_of_date = date.fromisoformat(str(fixture.params["as_of_date"]))
    run_id = str(fixture.params["run_id"])
    desk_id = str(fixture.params["desk_id"])

    risk_factors_by_name = {risk_factor.name: risk_factor for risk_factor in fixture.risk_factors}
    classifications = _classifications(fixture, policy)
    routing = route_nmrf_classifications_for_capital(classifications, policy)

    imcc_cube = _filtered_cube(fixture.scenario_cube, routing.imcc_risk_factors)
    imcc_risk_factors = tuple(risk_factors_by_name[name] for name in imcc_cube.risk_factor_names)
    nested_vectors = imcc_nested_lh_vectors_from_cube(imcc_cube, imcc_risk_factors)
    imcc_result = imcc_breakdown_for_policy(
        nested_vectors.all_risk_class_vectors,
        nested_vectors.per_risk_class_vectors,
        policy,
        run_id=run_id,
        desk_id=desk_id,
    )

    stress_selection = select_stress_periods_for_policy(
        fixture.stress_histories,
        policy,
        as_of_date=as_of_date,
        run_id=run_id,
        desk_id=desk_id,
    )
    validate_selected_stress_periods(
        stress_selection,
        tuple(risk_factors_by_name[name].risk_class for name in routing.ses_risk_factors),
    )

    method_evidence = _method_evidence_from_fixture(fixture.nmrf_evidence)
    selection_inputs = tuple(
        selection_input_from_method_evidence(
            method_evidence[name],
            classifications[name],
            risk_factors_by_name[name].liquidity_horizon,
        )
        for name in routing.ses_risk_factors
    )
    decisions = select_nmrf_methods(selection_inputs, policy)
    specs = build_nmrf_valuation_specs(
        tuple(decision.to_valuation_instruction() for decision in decisions),
        {risk_factor.name: risk_factor.risk_class for risk_factor in fixture.risk_factors},
        stress_period_specs_for_nmrf(stress_selection),
        policy,
        direct_shocks=_direct_shocks_from_fixture(fixture.nmrf_evidence),
        full_revaluations=_full_revaluations_from_fixture(fixture.nmrf_evidence),
        source="fixture NMRF valuation spec builder",
    )
    artifacts = _artifacts_from_fixture_arrays(specs, fixture.nmrf_artifacts)
    valuation_request = build_nmrf_valuation_run_request(
        specs,
        policy,
        run_id=run_id,
        desk_id=desk_id,
        as_of_date=as_of_date,
    )
    valuation_run = complete_nmrf_valuation_run(valuation_request, artifacts)
    nmrf_capital = calculate_nmrf_capital_from_valuation_run(
        classifications,
        valuation_run,
        policy,
    )

    observation_dates = tuple(
        date.fromisoformat(str(value))
        for value in fixture.pla_bt_vectors["observation_dates"].tolist()
    )
    pla_result = pla_assessment_for_policy_with_diagnostics(
        fixture.pla_bt_vectors["hpl"],
        fixture.pla_bt_vectors["rtpl"],
        policy,
        observation_dates=observation_dates,
        run_id=run_id,
        desk_id=desk_id,
    )
    backtest_result = trading_desk_backtest_trace_for_policy(
        fixture.pla_bt_vectors["apl"],
        fixture.pla_bt_vectors["hpl"],
        {
            0.975: fixture.pla_bt_vectors["var_975"],
            0.99: fixture.pla_bt_vectors["var_99"],
        },
        policy,
        observation_dates=observation_dates,
        run_id=run_id,
        desk_id=desk_id,
    )
    level_99 = backtest_result.result.level(0.99)
    multiplier = supervisory_multiplier_for_policy(level_99.apl_exceptions, policy)
    capital = models_based_capital(
        imcc_t_minus_1=imcc_result.imcc,
        ses_t_minus_1=nmrf_capital.total_ses,
        imcc_60d_avg=imcc_result.imcc * 1.03,
        ses_60d_avg=nmrf_capital.total_ses * 1.02,
        multiplier=multiplier,
        pla_addon=0.0,
    )

    return {
        "scalars": {
            "imcc": imcc_result.imcc,
            "unconstrained_lha_es": imcc_result.unconstrained_lha_es,
            "constrained_lha_es": imcc_result.constrained_lha_es,
            "total_ses": nmrf_capital.total_ses,
            "pla_ks_statistic": pla_result.ks_statistic,
            "models_based_capital": capital.models_based_capital,
            "supervisory_multiplier": multiplier,
        },
        "classifications": {name: classifications[name].value for name in sorted(classifications)},
        "nmrf_methods": {
            decision.risk_factor_name: decision.method.value for decision in decisions
        },
        "selected_stress_periods": {
            risk_class.value: stress_selection.selected_by_risk_class[risk_class].period_id
            for risk_class in sorted(
                stress_selection.selected_by_risk_class,
                key=lambda item: item.value,
            )
        },
        "reconciliation": {
            "passed": valuation_run.passed,
            "failed_item_count": valuation_run.reconciliation.failed_item_count,
            "artifact_count": valuation_run.reconciliation.artifact_count,
        },
        "pla": {
            "zone": pla_result.zone,
            "window_size": pla_result.diagnostics.window_size,
        },
        "backtesting": {
            "model_eligible": backtest_result.model_eligible,
            "window_size": backtest_result.window_size,
            "levels": {
                str(level.confidence_level): {
                    "apl_exceptions": level.apl_exceptions,
                    "hpl_exceptions": level.hpl_exceptions,
                    "level_passed": level.level_passed,
                }
                for level in backtest_result.result.levels
            },
        },
        "capital": {"binding_term": capital.binding_term},
    }


def _classifications(
    fixture: CapitalRunFixture,
    policy: RegulatoryPolicy,
) -> dict[str, ModellabilityStatus]:
    assessments = {
        risk_factor.name: assess_rfet_evidence(
            risk_factor,
            fixture.rfet_evidence[risk_factor.name],
            policy,
        )
        for risk_factor in fixture.risk_factors
    }
    return {
        risk_factor_name: assessment.modellability_status
        for risk_factor_name, assessment in assessments.items()
    }


def _method_evidence_from_fixture(
    raw_evidence: Mapping[str, object],
) -> dict[str, NMRFMethodEvidence]:
    evidence_by_name: dict[str, NMRFMethodEvidence] = {}
    for risk_factor_name, raw in raw_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        robustness = None
        check = raw.get("direct_robustness_check")
        if isinstance(check, Mapping):
            robustness = assess_direct_loss_robustness(
                check["direct_losses"],
                check["benchmark_losses"],
                max_relative_error_threshold=float(check["max_relative_error_threshold"]),
                source=str(check["source"]),
            )
        evidence_by_name[risk_factor_name] = NMRFMethodEvidence(
            risk_factor_name=risk_factor_name,
            nonlinear=bool(raw.get("nonlinear", False)),
            full_revaluation_available=bool(raw.get("full_revaluation_available", False)),
            direct_method_available=bool(raw.get("direct_method_available", False)),
            direct_shock_well_defined=bool(raw.get("direct_shock_well_defined", False)),
            direct_robustness=robustness,
            stepwise_available=bool(raw.get("stepwise_available", False)),
            stepwise_required=bool(raw.get("stepwise_required", False)),
            max_loss_fallback_allowed=bool(raw.get("max_loss_fallback_allowed", False)),
            pricing_attempt_count=int(raw.get("pricing_attempt_count", 0)),
            pricing_failure_count=int(raw.get("pricing_failure_count", 0)),
            proxy_or_basis_risk=bool(raw.get("proxy_or_basis_risk", False)),
            source=str(raw.get("source", "")),
        )
    return evidence_by_name


def _direct_shocks_from_fixture(
    raw_evidence: Mapping[str, object],
) -> dict[str, NMRFDirectShockSpec]:
    result: dict[str, NMRFDirectShockSpec] = {}
    for risk_factor_name, raw in raw_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        shock = raw.get("direct_shock")
        if not isinstance(shock, Mapping):
            continue
        result[risk_factor_name] = NMRFDirectShockSpec(
            shock_size=float(shock["shock_size"]),
            shock_unit=str(shock["shock_unit"]),
            direction=NMRFShockDirection(str(shock["direction"])),
            calibration_source=str(shock["calibration_source"]),
            confidence_level=float(shock["confidence_level"]),
            notes=str(shock.get("notes", "")),
        )
    return result


def _full_revaluations_from_fixture(
    raw_evidence: Mapping[str, object],
) -> dict[str, NMRFFullRevaluationSpec]:
    result: dict[str, NMRFFullRevaluationSpec] = {}
    for risk_factor_name, raw in raw_evidence.items():
        if not isinstance(raw, Mapping):
            raise TypeError(f"NMRF evidence for {risk_factor_name} must be a mapping")
        revaluation = raw.get("full_revaluation")
        if not isinstance(revaluation, Mapping):
            continue
        result[risk_factor_name] = NMRFFullRevaluationSpec(
            scenario_set_id=str(revaluation["scenario_set_id"]),
            market_state_ids=tuple(str(item) for item in revaluation["market_state_ids"]),
            calibration_source=str(revaluation["calibration_source"]),
            require_full_trade_repricing=bool(
                revaluation.get("require_full_trade_repricing", True)
            ),
            notes=str(revaluation.get("notes", "")),
        )
    return result


def _artifacts_from_fixture_arrays(
    specs: Sequence[NMRFValuationSpec],
    arrays: Mapping[str, np.ndarray[Any, Any]],
) -> tuple[NMRFStressArtifact, ...]:
    artifacts: list[NMRFStressArtifact] = []
    for spec in specs:
        risk_factor_name = str(spec.risk_factor_name)
        artifacts.append(
            NMRFStressArtifact(
                risk_factor_name=risk_factor_name,
                method=spec.method,
                losses=arrays[f"{risk_factor_name}_losses"],
                liquidity_horizon=LiquidityHorizon(spec.required_liquidity_horizon),
                stress_period=spec.stress_period.stress_period_id,
                source="fixture upstream valuation artifact",
                scenario_ids=tuple(
                    str(item) for item in arrays[f"{risk_factor_name}_scenario_ids"].tolist()
                ),
                generated_by_prototype=False,
            )
        )
    return tuple(artifacts)


def _filtered_cube(cube: ScenarioCube, risk_factor_names: Sequence[str]) -> ScenarioCube:
    allowed = set(risk_factor_names)
    selected = tuple(name for name in cube.risk_factor_names if name in allowed)
    indices = [cube.risk_factor_index[name] for name in selected]
    values = cube.values[:, :, indices].copy()
    values.flags.writeable = False
    return ScenarioCube(
        values=values,
        scenario_metadata=cube.scenario_metadata,
        position_ids=cube.position_ids,
        risk_factor_names=selected,
        name=f"{cube.name}_filtered_imcc",
    )


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
