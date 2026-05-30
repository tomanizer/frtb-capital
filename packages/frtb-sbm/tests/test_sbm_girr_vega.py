from __future__ import annotations

import importlib.util
import json
import math
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    girr_vega_intra_bucket_correlation,
    girr_vega_liquidity_horizon_days,
    serialize_sbm_result,
    vega_risk_weight,
    weight_girr_vega_sensitivities,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "girr_vega_v1"
_RISK_CLASS_KEYS = ("risk_class", "risk_measure", "selected_capital", "selected_scenario")
_BUCKET_KEYS = ("bucket_id", "kb", "sb")
_WEIGHTED_KEYS = ("sensitivity_id", "risk_weight", "scaled_amount")


def sample_lineage(row_id: str = "row-001") -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
    )


def sample_vega_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "vega-001",
        "source_row_id": "row-001",
        "desk_id": "rates-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.GIRR,
        "risk_measure": SbmRiskMeasure.VEGA,
        "bucket": "2",
        "risk_factor": "USD",
        "amount": 100_000.0,
        "amount_currency": "USD",
        "tenor": "5y",
        "option_tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_lineage(),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("girr_vega_v1_loader", FIXTURE_DIR / "loader.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_girr_vega_liquidity_horizon_and_risk_weight() -> None:
    horizon = girr_vega_liquidity_horizon_days(SbmRegulatoryProfile.BASEL_MAR21)

    assert horizon == 60
    risk_weight, citation_ids = vega_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        liquidity_horizon_days=horizon,
    )
    expected = min(1.0, 0.55 * math.sqrt(horizon / 10.0))
    assert risk_weight == pytest.approx(expected)
    assert risk_weight == 1.0
    assert citation_ids == ("basel_mar21_92",)


def test_girr_vega_intra_bucket_correlation_uses_option_and_underlying_tenors() -> None:
    correlation, citation_ids = girr_vega_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        option_tenor1="1y",
        option_tenor2="5y",
        tenor1="1y",
        tenor2="5y",
    )
    rho_opt = math.exp(-0.01 * abs(1.0 - 5.0) / 1.0)
    rho_ul = math.exp(-0.01 * abs(1.0 - 5.0) / 1.0)

    assert correlation == pytest.approx(min(1.0, rho_opt * rho_ul))
    assert citation_ids == ("basel_mar21_93",)


def test_weight_girr_vega_applies_cited_risk_weight() -> None:
    weighted = weight_girr_vega_sensitivities(
        (sample_vega_sensitivity(),),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert len(weighted) == 1
    item = weighted[0]
    assert item.risk_weight == 1.0
    assert item.scaled_amount == pytest.approx(100_000.0)
    assert item.liquidity_horizon_days == 60
    assert "basel_mar21_92" in item.citation_ids


def test_calculate_sbm_capital_supports_girr_vega_only_inputs() -> None:
    context = SbmCalculationContext(
        run_id="vega-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    result = calculate_sbm_capital((sample_vega_sensitivity(),), context=context)

    assert len(result.risk_classes) == 1
    girr = result.risk_classes[0]
    assert girr.risk_measure is SbmRiskMeasure.VEGA
    assert result.total_capital == girr.selected_capital


def test_girr_vega_v1_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    payload = serialize_sbm_result(result)

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_capital"] == expected["total_capital"]
    risk_class_payload = [
        _select(risk_class, _RISK_CLASS_KEYS) for risk_class in payload["risk_classes"]
    ]
    assert risk_class_payload == expected["risk_classes"]
    assert [
        [_select(bucket, _BUCKET_KEYS) for bucket in risk_class["buckets"]]
        for risk_class in payload["risk_classes"]
    ] == expected["buckets"]
    assert [
        [
            [_select(item, _WEIGHTED_KEYS) for item in bucket["weighted_sensitivities"]]
            for bucket in risk_class["buckets"]
        ]
        for risk_class in payload["risk_classes"]
    ] == expected["weighted_sensitivities"]


def test_girr_vega_v1_fixture_result_is_replay_stable() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    first = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    second = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def _select(payload: object, keys: tuple[str, ...]) -> dict[str, object]:
    assert isinstance(payload, dict)
    return {key: payload[key] for key in keys}
