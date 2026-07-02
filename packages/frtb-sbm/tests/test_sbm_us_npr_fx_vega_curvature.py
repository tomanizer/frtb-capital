from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pyarrow as pa
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    curvature_citation_ids,
    curvature_risk_weight,
    non_girr_vega_intra_bucket_correlation,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
    vega_liquidity_horizon_days,
    vega_risk_weight,
)
from sbm_registry_helpers import (
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_RISK_CLASS_KEYS = ("risk_class", "risk_measure", "selected_capital", "selected_scenario")
_BUCKET_KEYS = ("bucket_id", "kb", "sb")
_WEIGHTED_KEYS = ("sensitivity_id", "risk_weight", "scaled_amount")
_BRANCH_KEYS = (
    "bucket_id",
    "scenario",
    "selected_branch",
    "selected_bucket_capital",
    "rejected_branch",
    "rejected_bucket_capital",
)


def load_fixture_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{name}_loader",
        FIXTURE_ROOT / name / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_us_npr_fx_vega_reference_data_uses_npr_citations() -> None:
    horizon = vega_liquidity_horizon_days(
        SbmRegulatoryProfile.US_NPR_2_0,
        risk_class=SbmRiskClass.FX,
    )
    risk_weight, weight_citations = vega_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        risk_class=SbmRiskClass.FX,
        liquidity_horizon_days=horizon,
    )
    correlation, correlation_citations = non_girr_vega_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0.value,
        risk_class=SbmRiskClass.FX,
        bucket_id="EUR",
        risk_factor_a="EUR",
        risk_factor_b="EUR",
        option_tenor_a="1y",
        option_tenor_b="5y",
    )

    assert horizon == 40
    assert risk_weight == 1.0
    assert weight_citations == ("us_npr_91_fr_14952_va7a_fx_vega_lh_rw",)
    assert correlation > 0.0
    assert correlation_citations == (
        "us_npr_91_fr_14952_va7a_sbm_scope",
        "us_npr_91_fr_14952_va7a_fx_vega_intra",
        "us_npr_91_fr_14952_va7a_fx_delta_intra",
        "us_npr_91_fr_14952_va7a_fx_vega_option_tenors",
    )


def test_us_npr_fx_curvature_reference_data_uses_npr_citations() -> None:
    citation_ids = curvature_citation_ids(
        SbmRegulatoryProfile.US_NPR_2_0,
        SbmRiskClass.FX,
    )
    risk_weight, weight_citations = curvature_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        risk_class=SbmRiskClass.FX,
        currency="EUR",
        reporting_currency="USD",
    )

    assert risk_weight == pytest.approx(0.15 / 2**0.5)
    assert citation_ids == (
        "us_npr_91_fr_14952_va7a_fx_curvature_factors",
        "us_npr_91_fr_14952_va7a_fx_curvature_shocks",
        "us_npr_91_fr_14952_va7a_fx_curvature_intra",
        "us_npr_91_fr_14952_va7a_fx_curvature_inter",
        "us_npr_91_fr_14952_va7a_fx_curvature_scenarios",
    )
    assert weight_citations == (
        "us_npr_91_fr_14952_va7a_fx_curvature_shocks",
        "us_npr_91_fr_14952_va7a_fx_delta_weights",
        "us_npr_91_fr_14952_va7a_fx_delta_sqrt2",
    )


def test_us_npr_fx_vega_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module("fx_vega_us_npr_v1")
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_capital"] == expected["total_capital"]
    assert payload["warnings"] == expected["warnings"]
    assert payload["selected_portfolio_scenario"] == expected["selected_portfolio_scenario"]
    assert payload["portfolio_scenario_totals"] == expected["portfolio_scenario_totals"]
    assert [
        _select(item, (*_RISK_CLASS_KEYS, "citation_ids")) for item in payload["risk_classes"]
    ] == expected["risk_classes"]
    assert payload["risk_classes"][0]["scenario_totals"] == expected["scenario_totals"]
    assert [
        [_select(bucket, (*_BUCKET_KEYS, "citation_ids")) for bucket in risk_class["buckets"]]
        for risk_class in payload["risk_classes"]
    ] == expected["buckets"]
    assert [
        [
            [
                _select(item, (*_WEIGHTED_KEYS, "citation_ids"))
                for item in bucket["weighted_sensitivities"]
            ]
            for bucket in risk_class["buckets"]
        ]
        for risk_class in payload["risk_classes"]
    ] == expected["weighted_sensitivities"]
    assert not _contains_basel_citation(payload)


def test_us_npr_fx_vega_batch_and_arrow_match_row_result() -> None:
    loader = load_fixture_module("fx_vega_us_npr_v1")
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.VEGA)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    handoff = normalize_sbm_path(
        SbmRiskClass.FX,
        SbmRiskMeasure.VEGA,
        _vega_arrow_table(sensitivities),
    )
    arrow_payload = serialize_sbm_result(
        calculate_sbm_capital_from_path_arrow(
            SbmRiskClass.FX, SbmRiskMeasure.VEGA, handoff, context=context
        )
    )

    assert batch_payload == row_payload
    assert arrow_payload["total_capital"] == row_payload["total_capital"]
    assert arrow_payload["profile_hash"] == row_payload["profile_hash"]
    assert arrow_payload["risk_classes"] == row_payload["risk_classes"]


def test_us_npr_fx_curvature_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module("fx_curvature_us_npr_v1")
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_capital"] == expected["total_capital"]
    assert payload["warnings"] == expected["warnings"]
    assert payload["selected_portfolio_scenario"] == expected["selected_portfolio_scenario"]
    assert payload["portfolio_scenario_totals"] == expected["portfolio_scenario_totals"]
    assert [
        _select(item, (*_RISK_CLASS_KEYS, "citation_ids")) for item in payload["risk_classes"]
    ] == expected["risk_classes"]
    assert payload["risk_classes"][0]["scenario_totals"] == expected["scenario_totals"]
    assert [
        [_select(bucket, (*_BUCKET_KEYS, "citation_ids")) for bucket in risk_class["buckets"]]
        for risk_class in payload["risk_classes"]
    ] == expected["buckets"]
    assert [
        [
            [
                _select(item, (*_WEIGHTED_KEYS, "citation_ids"))
                for item in bucket["weighted_sensitivities"]
            ]
            for bucket in risk_class["buckets"]
        ]
        for risk_class in payload["risk_classes"]
    ] == expected["weighted_sensitivities"]
    assert [
        _select(
            branch,
            (
                "sensitivity_id",
                "selected_branch",
                "up_shock_amount",
                "down_shock_amount",
                "citation_ids",
            ),
        )
        for branch in payload["risk_classes"][0]["curvature_branches"]
    ] == expected["curvature_branches"]
    assert [
        _select(branch, (*_BRANCH_KEYS, "citation_ids"))
        for branch in payload["risk_classes"][0]["curvature_bucket_branches"]
    ] == expected["curvature_bucket_branches"]
    assert not _contains_basel_citation(payload)


def test_us_npr_fx_curvature_batch_and_arrow_match_row_result() -> None:
    loader = load_fixture_module("fx_curvature_us_npr_v1")
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.CURVATURE)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    handoff = normalize_sbm_path(
        SbmRiskClass.FX,
        SbmRiskMeasure.CURVATURE,
        _curvature_arrow_table(sensitivities),
    )
    arrow_payload = serialize_sbm_result(
        calculate_sbm_capital_from_path_arrow(
            SbmRiskClass.FX, SbmRiskMeasure.CURVATURE, handoff, context=context
        )
    )

    assert batch_payload == row_payload
    assert arrow_payload["total_capital"] == row_payload["total_capital"]
    assert arrow_payload["profile_hash"] == row_payload["profile_hash"]
    assert arrow_payload["risk_classes"] == row_payload["risk_classes"]


def test_us_npr_fx_curvature_branch_records_preserve_supplied_shock_ids() -> None:
    loader = load_fixture_module("fx_curvature_us_npr_v1")
    context = loader.load_fixture_context()
    base_sensitivities = loader.load_fixture_sensitivities()
    sensitivities = tuple(
        replace(
            sensitivity,
            up_shock_id=f"shock-up-{index}",
            down_shock_id=f"shock-down-{index}",
            surface_id="surface-fx-option-curvature",
            surface_point_id=f"surface-fx-option-curvature:{index}",
        )
        for index, sensitivity in enumerate(base_sensitivities, start=1)
    )

    base_result = calculate_sbm_capital(base_sensitivities, context=context)
    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.CURVATURE)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    row_branches = _curvature_branch_payloads(row_payload)
    batch_branches = _curvature_branch_payloads(batch_payload)
    branches_by_id = {
        branch["sensitivity_id"]: branch
        for branch in row_branches
        if isinstance(branch["sensitivity_id"], str)
    }

    assert row_payload["total_capital"] == pytest.approx(base_result.total_capital)
    assert batch_branches == row_branches
    for index, sensitivity in enumerate(sensitivities, start=1):
        branch = branches_by_id[sensitivity.sensitivity_id]
        assert branch["up_shock_id"] == f"shock-up-{index}"
        assert branch["down_shock_id"] == f"shock-down-{index}"
        assert branch["surface_id"] == "surface-fx-option-curvature"
        assert branch["surface_point_id"] == f"surface-fx-option-curvature:{index}"


@pytest.mark.parametrize(
    ("fixture_name", "case_id", "expected_error_match", "sensitivities"),
    [
        (fixture_name, *case)
        for fixture_name in ("fx_vega_us_npr_v1", "fx_curvature_us_npr_v1")
        for case in load_fixture_module(fixture_name).load_invalid_cases()
    ],
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_us_npr_fx_vega_curvature_unsupported_fixture_cases_fail_closed(
    fixture_name: str,
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module(fixture_name)
    context = loader.load_fixture_context()

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id


def _vega_arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": [item.risk_class.value for item in sensitivities],
            "risk_measure": [item.risk_measure.value for item in sensitivities],
            "bucket": [item.bucket for item in sensitivities],
            "risk_factor": [item.risk_factor for item in sensitivities],
            "amount": [item.amount for item in sensitivities],
            "amount_currency": [item.amount_currency for item in sensitivities],
            "sign_convention": [item.sign_convention.value for item in sensitivities],
            "option_tenor": [item.option_tenor for item in sensitivities],
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _curvature_arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": [item.risk_class.value for item in sensitivities],
            "risk_measure": [item.risk_measure.value for item in sensitivities],
            "bucket": [item.bucket for item in sensitivities],
            "risk_factor": [item.risk_factor for item in sensitivities],
            "amount": [item.amount for item in sensitivities],
            "amount_currency": [item.amount_currency for item in sensitivities],
            "sign_convention": [item.sign_convention.value for item in sensitivities],
            "up_shock_amount": [item.up_shock_amount for item in sensitivities],
            "down_shock_amount": [item.down_shock_amount for item in sensitivities],
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _curvature_branch_payloads(payload: dict[str, object]) -> list[dict[str, object]]:
    risk_classes = payload["risk_classes"]
    assert isinstance(risk_classes, list)
    first_risk_class = risk_classes[0]
    assert isinstance(first_risk_class, dict)
    branches = first_risk_class["curvature_branches"]
    assert isinstance(branches, list)
    for branch in branches:
        assert isinstance(branch, dict)
    return branches


def _select(payload: object, keys: tuple[str, ...]) -> dict[str, object]:
    assert isinstance(payload, dict)
    return {key: payload[key] for key in keys}


def _contains_basel_citation(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_contains_basel_citation(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_basel_citation(value) for value in payload)
    return isinstance(payload, str) and payload.startswith("basel_")
