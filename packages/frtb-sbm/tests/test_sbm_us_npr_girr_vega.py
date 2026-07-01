from __future__ import annotations

import importlib.util
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
    girr_vega_intra_bucket_correlation,
    girr_vega_liquidity_horizon_days,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
    vega_risk_weight,
)
from sbm_registry_helpers import (
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "girr_vega_us_npr_v1"
_RISK_CLASS_KEYS = ("risk_class", "risk_measure", "selected_capital", "selected_scenario")
_BUCKET_KEYS = ("bucket_id", "kb", "sb")
_WEIGHTED_KEYS = ("sensitivity_id", "risk_weight", "scaled_amount")
_CITATION_KEYS = (*_RISK_CLASS_KEYS, "citation_ids")


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "girr_vega_us_npr_v1_loader",
        FIXTURE_DIR / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_us_npr_girr_vega_reference_data_uses_npr_citations() -> None:
    horizon = girr_vega_liquidity_horizon_days(SbmRegulatoryProfile.US_NPR_2_0)
    risk_weight, weight_citations = vega_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        liquidity_horizon_days=horizon,
    )
    correlation, correlation_citations = girr_vega_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        option_tenor1="1y",
        option_tenor2="5y",
        tenor1="1y",
        tenor2="5y",
    )

    assert horizon == 60
    assert risk_weight == 1.0
    assert weight_citations == ("us_npr_91_fr_14952_va7a_girr_vega_lh_rw",)
    assert correlation > 0.0
    assert correlation_citations == ("us_npr_91_fr_14952_va7a_girr_vega_intra",)


def test_us_npr_girr_vega_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module()
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
    assert [_select(item, _CITATION_KEYS) for item in payload["risk_classes"]] == expected[
        "risk_classes"
    ]
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


def test_us_npr_girr_vega_batch_and_arrow_match_row_result() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.VEGA)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    handoff = normalize_sbm_path(
        SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, _arrow_table(sensitivities)
    )
    arrow_payload = serialize_sbm_result(
        calculate_sbm_capital_from_path_arrow(
            SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, handoff, context=context
        )
    )

    assert batch_payload == row_payload
    assert arrow_payload["total_capital"] == row_payload["total_capital"]
    assert arrow_payload["profile_hash"] == row_payload["profile_hash"]
    assert arrow_payload["risk_classes"] == row_payload["risk_classes"]


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_fixture_module().load_invalid_cases(),
    ids=lambda case: str(case[0]),
)
def test_us_npr_girr_vega_unsupported_fixture_cases_fail_closed(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id


def _arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
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
            "tenor": [item.tenor for item in sensitivities],
            "option_tenor": [item.option_tenor for item in sensitivities],
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _select(payload: object, keys: tuple[str, ...]) -> dict[str, object]:
    assert isinstance(payload, dict)
    return {key: payload[key] for key in keys}


def _contains_basel_citation(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_contains_basel_citation(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_basel_citation(value) for value in payload)
    return isinstance(payload, str) and payload.startswith("basel_")
