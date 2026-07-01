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
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
)
from frtb_sbm.reference_data import (
    commodity_delta_intra_bucket_correlation,
    commodity_delta_risk_weight,
    commodity_inter_bucket_correlation,
    equity_delta_intra_bucket_correlation,
    equity_delta_risk_weight,
    equity_inter_bucket_correlation,
)
from sbm_registry_helpers import (
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_RISK_CLASS_KEYS = ("risk_class", "risk_measure", "selected_capital", "selected_scenario")
_BUCKET_KEYS = ("bucket_id", "kb", "sb")
_WEIGHTED_KEYS = ("sensitivity_id", "risk_weight", "scaled_amount")


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


def test_us_npr_equity_delta_reference_data_uses_npr_citations() -> None:
    risk_weight, weight_citations = equity_delta_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="5",
        risk_factor="SPOT",
    )
    intra, intra_citations = equity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="5",
        risk_factor_a="SPOT",
        risk_factor_b="SPOT",
        issuer_a="ISS-A",
        issuer_b="ISS-B",
    )
    inter, inter_citations = equity_inter_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="5",
        bucket2="6",
    )

    assert risk_weight == pytest.approx(0.30)
    assert weight_citations == ("us_npr_91_fr_14952_va7a_equity_delta_weights",)
    assert intra == pytest.approx(0.25)
    assert intra_citations == ("us_npr_91_fr_14952_va7a_equity_delta_intra",)
    assert inter == pytest.approx(0.15)
    assert inter_citations == ("us_npr_91_fr_14952_va7a_equity_delta_inter",)


def test_us_npr_commodity_delta_reference_data_uses_npr_citations() -> None:
    risk_weight, weight_citations = commodity_delta_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="12",
    )
    intra, intra_citations = commodity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket_id="12",
        commodity_a="INDEX-A",
        commodity_b="INDEX-B",
        tenor_a="3m",
        tenor_b="3m",
        location_a="GLOBAL",
        location_b="GLOBAL",
    )
    inter, inter_citations = commodity_inter_bucket_correlation(
        SbmRegulatoryProfile.US_NPR_2_0,
        bucket1="2",
        bucket2="12",
    )

    assert risk_weight == pytest.approx(0.30)
    assert weight_citations == ("us_npr_91_fr_14952_va7a_commodity_delta_weights",)
    assert intra == pytest.approx(0.50)
    assert intra_citations == ("us_npr_91_fr_14952_va7a_commodity_delta_intra",)
    assert inter == pytest.approx(0.20)
    assert inter_citations == ("us_npr_91_fr_14952_va7a_commodity_delta_inter",)


@pytest.mark.parametrize(
    ("fixture_name", "risk_class"),
    [
        ("equity_delta_us_npr_v1", SbmRiskClass.EQUITY),
        ("commodity_delta_us_npr_v1", SbmRiskClass.COMMODITY),
    ],
)
def test_us_npr_equity_commodity_delta_fixtures_match_expected_outputs(
    fixture_name: str,
    risk_class: SbmRiskClass,
) -> None:
    loader = load_fixture_module(fixture_name)
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
    assert payload["risk_classes"][0]["risk_class"] == risk_class.value
    assert [
        _select(item, (*_RISK_CLASS_KEYS, "citation_ids")) for item in payload["risk_classes"]
    ] == expected["risk_classes"]
    assert payload["risk_classes"][0]["scenario_totals"] == expected["scenario_totals"]
    assert [
        [
            _select(bucket, (*_BUCKET_KEYS, "citation_ids"))
            for bucket in risk_class_payload["buckets"]
        ]
        for risk_class_payload in payload["risk_classes"]
    ] == expected["buckets"]
    assert [
        [
            [
                _select(item, (*_WEIGHTED_KEYS, "citation_ids"))
                for item in bucket["weighted_sensitivities"]
            ]
            for bucket in risk_class_payload["buckets"]
        ]
        for risk_class_payload in payload["risk_classes"]
    ] == expected["weighted_sensitivities"]
    assert not _contains_basel_citation(payload)


@pytest.mark.parametrize(
    ("fixture_name", "risk_class"),
    [
        ("equity_delta_us_npr_v1", SbmRiskClass.EQUITY),
        ("commodity_delta_us_npr_v1", SbmRiskClass.COMMODITY),
    ],
)
def test_us_npr_equity_commodity_delta_batch_and_arrow_match_row_result(
    fixture_name: str,
    risk_class: SbmRiskClass,
) -> None:
    loader = load_fixture_module(fixture_name)
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, risk_class, SbmRiskMeasure.DELTA)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    handoff = normalize_sbm_path(
        risk_class,
        SbmRiskMeasure.DELTA,
        _delta_arrow_table(sensitivities, include_tenor=risk_class is SbmRiskClass.COMMODITY),
    )
    arrow_payload = serialize_sbm_result(
        calculate_sbm_capital_from_path_arrow(
            risk_class,
            SbmRiskMeasure.DELTA,
            handoff,
            context=context,
        )
    )

    assert batch_payload == row_payload
    assert arrow_payload["total_capital"] == row_payload["total_capital"]
    assert arrow_payload["profile_hash"] == row_payload["profile_hash"]
    assert arrow_payload["risk_classes"] == row_payload["risk_classes"]


@pytest.mark.parametrize(
    ("fixture_name", "case_id", "expected_error_match", "sensitivities"),
    [
        (fixture_name, *case)
        for fixture_name in ("equity_delta_us_npr_v1", "commodity_delta_us_npr_v1")
        for case in load_fixture_module(fixture_name).load_invalid_cases()
    ],
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_us_npr_equity_commodity_delta_unsupported_fixture_cases_fail_closed(
    fixture_name: str,
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module(fixture_name)
    context = loader.load_fixture_context()
    fixture_risk_class = (
        SbmRiskClass.EQUITY if fixture_name == "equity_delta_us_npr_v1" else SbmRiskClass.COMMODITY
    )

    assert context.profile_id == SbmRegulatoryProfile.US_NPR_2_0.value
    assert any(sensitivity.risk_class is fixture_risk_class for sensitivity in sensitivities)

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id


def _delta_arrow_table(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    include_tenor: bool,
) -> pa.Table:
    payload = {
        "sensitivity_id": [item.sensitivity_id for item in sensitivities],
        "source_row_id": [item.source_row_id for item in sensitivities],
        "desk_id": [item.desk_id for item in sensitivities],
        "legal_entity": [item.legal_entity for item in sensitivities],
        "risk_class": [item.risk_class.value for item in sensitivities],
        "risk_measure": [item.risk_measure.value for item in sensitivities],
        "bucket": [item.bucket for item in sensitivities],
        "risk_factor": [item.risk_factor for item in sensitivities],
        "qualifier": [item.qualifier for item in sensitivities],
        "amount": [item.amount for item in sensitivities],
        "amount_currency": [item.amount_currency for item in sensitivities],
        "sign_convention": [item.sign_convention.value for item in sensitivities],
        "lineage_source_system": [item.lineage.source_system for item in sensitivities],
        "lineage_source_file": [item.lineage.source_file for item in sensitivities],
    }
    if include_tenor:
        payload["tenor"] = [item.tenor for item in sensitivities]
    return pa.table(payload)


def _select(payload: object, keys: tuple[str, ...]) -> dict[str, object]:
    assert isinstance(payload, dict)
    return {key: payload[key] for key in keys}


def _contains_basel_citation(payload: object) -> bool:
    if isinstance(payload, dict):
        return any(_contains_basel_citation(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_basel_citation(value) for value in payload)
    return isinstance(payload, str) and payload.startswith("basel_")
