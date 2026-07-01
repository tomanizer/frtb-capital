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
    curvature_citation_ids,
    curvature_risk_weight,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
)
from sbm_registry_helpers import (
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "girr_curvature_us_npr_v1"
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


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "girr_curvature_us_npr_v1_loader",
        FIXTURE_DIR / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_us_npr_girr_curvature_reference_data_uses_npr_citations() -> None:
    citation_ids = curvature_citation_ids(SbmRegulatoryProfile.US_NPR_2_0)
    risk_weight, weight_citations = curvature_risk_weight(
        SbmRegulatoryProfile.US_NPR_2_0,
        risk_class=SbmRiskClass.GIRR,
    )

    assert risk_weight == pytest.approx(0.017)
    assert "us_npr_91_fr_14952_va7a_girr_curvature_shocks" in citation_ids
    assert "basel_mar21_99" not in weight_citations
    assert weight_citations == (
        "us_npr_91_fr_14952_va7a_girr_curvature_shocks",
        "us_npr_91_fr_14952_va7a_girr_delta_weights",
    )


def test_us_npr_girr_curvature_fixture_matches_expected_outputs() -> None:
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


def test_us_npr_girr_curvature_batch_and_arrow_match_row_result() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    row_payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE)
    batch_payload = serialize_sbm_result(calculate_sbm_capital_from_batch(batch, context=context))
    handoff = normalize_sbm_path(
        SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, _arrow_table(sensitivities)
    )
    arrow_payload = serialize_sbm_result(
        calculate_sbm_capital_from_path_arrow(
            SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, handoff, context=context
        )
    )

    assert batch_payload == row_payload
    assert arrow_payload["total_capital"] == row_payload["total_capital"]
    assert arrow_payload["profile_hash"] == row_payload["profile_hash"]
    assert arrow_payload["risk_classes"] == row_payload["risk_classes"]


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_fixture_module().load_invalid_cases(),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_us_npr_girr_curvature_unsupported_fixture_cases_fail_closed(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()

    assert context.profile_id == SbmRegulatoryProfile.US_NPR_2_0.value
    assert all(item.risk_measure is SbmRiskMeasure.CURVATURE for item in sensitivities)
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
            "up_shock_amount": [item.up_shock_amount for item in sensitivities],
            "down_shock_amount": [item.down_shock_amount for item in sensitivities],
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
