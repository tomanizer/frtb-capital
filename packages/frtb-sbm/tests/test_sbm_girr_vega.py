from __future__ import annotations

import importlib.util
import inspect
import json
import math
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import ModuleType

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import source_content_hash
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    girr_vega_intra_bucket_correlation,
    girr_vega_liquidity_horizon_days,
    input_hash_for_sensitivities,
    serialize_sbm_result,
    vega_risk_weight,
    weight_girr_vega_sensitivities,
    weight_girr_vega_sensitivity_batch,
)
from sbm_registry_helpers import (
    build_sbm_path_from_arrow,
    calculate_sbm_capital_from_path_arrow,
    normalize_sbm_path,
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


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="vega-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_vega_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        sample_vega_sensitivity(),
        sample_vega_sensitivity(
            sensitivity_id="vega-002",
            source_row_id="row-002",
            amount=50_000.0,
            tenor="10y",
            option_tenor="1y",
            lineage=sample_lineage("row-002"),
        ),
        sample_vega_sensitivity(
            sensitivity_id="vega-003",
            source_row_id="row-003",
            amount=-25_000.0,
            tenor="5y",
            option_tenor="1y",
            lineage=sample_lineage("row-003"),
        ),
    )


def sample_vega_arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": _dictionary([item.risk_class.value for item in sensitivities]),
            "risk_measure": _dictionary([item.risk_measure.value for item in sensitivities]),
            "bucket": _dictionary([item.bucket for item in sensitivities]),
            "risk_factor": _dictionary([item.risk_factor for item in sensitivities]),
            "amount": pa.array([item.amount for item in sensitivities], type=pa.float64()),
            "amount_currency": _dictionary([item.amount_currency for item in sensitivities]),
            "sign_convention": _dictionary([item.sign_convention.value for item in sensitivities]),
            "tenor": _dictionary([item.tenor for item in sensitivities]),
            "option_tenor": [item.option_tenor for item in sensitivities],
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


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


def test_girr_vega_result_preserves_surface_axis_metadata_without_changing_capital() -> None:
    base = sample_vega_sensitivity()
    with_surface = replace(
        base,
        maturity="5y",
        surface_id="surface-usd-swaption-vol",
        surface_point_id="surface-usd-swaption-vol:5y:5y",
    )

    base_result = calculate_sbm_capital((base,), context=sample_context())
    result = calculate_sbm_capital((with_surface,), context=sample_context())
    payload = serialize_sbm_result(result)
    risk_classes = payload["risk_classes"]
    assert isinstance(risk_classes, list)
    first_risk_class = risk_classes[0]
    assert isinstance(first_risk_class, dict)
    buckets = first_risk_class["buckets"]
    assert isinstance(buckets, list)
    first_bucket = buckets[0]
    assert isinstance(first_bucket, dict)
    weighted_sensitivities = first_bucket["weighted_sensitivities"]
    assert isinstance(weighted_sensitivities, list)
    weighted_payload = weighted_sensitivities[0]
    assert isinstance(weighted_payload, dict)

    assert result.total_capital == pytest.approx(base_result.total_capital)
    assert weighted_payload["underlying_tenor"] == "5y"
    assert weighted_payload["option_tenor"] == "5y"
    assert weighted_payload["maturity"] == "5y"
    assert weighted_payload["surface_id"] == "surface-usd-swaption-vol"
    assert weighted_payload["surface_point_id"] == "surface-usd-swaption-vol:5y:5y"


def test_calculate_sbm_capital_supports_girr_vega_only_inputs() -> None:
    context = sample_context()
    result = calculate_sbm_capital((sample_vega_sensitivity(),), context=context)

    assert len(result.risk_classes) == 1
    girr = result.risk_classes[0]
    assert girr.risk_measure is SbmRiskMeasure.VEGA
    assert result.total_capital == girr.selected_capital


def test_girr_vega_batch_and_handoff_match_row_capital() -> None:
    context = sample_context()
    sensitivities = sample_vega_sensitivities()
    source_hash = source_content_hash("synthetic GIRR vega source")
    handoff = normalize_sbm_path(
        SbmRiskClass.GIRR,
        SbmRiskMeasure.VEGA,
        sample_vega_arrow_table(sensitivities),
        source_hash=source_hash,
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    row_batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.VEGA)
    arrow_batch = build_sbm_path_from_arrow(SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, handoff)
    batch_result = calculate_sbm_capital_from_batch(arrow_batch, context=context)
    handoff_result = calculate_sbm_capital_from_path_arrow(
        SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, handoff, context=context
    )

    assert row_batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert len(arrow_batch.input_hash) == 64
    int(arrow_batch.input_hash, 16)
    assert arrow_batch.input_hash_algorithm == "arrow-columnar-v2"
    assert arrow_batch.input_hash != row_batch.input_hash
    assert arrow_batch.source_hash == source_hash
    assert arrow_batch.handoff_hash is not None
    np.testing.assert_array_equal(arrow_batch.sensitivity_ids, row_batch.sensitivity_ids)
    np.testing.assert_array_equal(arrow_batch.option_tenors, row_batch.option_tenors)
    assert len(batch_result.input_hash) == 64
    int(batch_result.input_hash, 16)
    assert batch_result.input_hash_algorithm == "arrow-columnar-v2"
    assert batch_result.input_hash != row_result.input_hash
    assert len(handoff_result.input_hash) == 64
    int(handoff_result.input_hash, 16)
    assert handoff_result.input_hash_algorithm == "arrow-columnar-v2"
    assert handoff_result.input_hash != row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.total_capital == pytest.approx(row_result.total_capital)
    assert batch_result.risk_classes[0].buckets == row_result.risk_classes[0].buckets
    assert "basel_mar21_93" in batch_result.risk_classes[0].citation_ids


def test_girr_vega_batch_keeps_option_and_underlying_tenor_axes() -> None:
    sensitivities = sample_vega_sensitivities()
    batch = build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.VEGA)

    weighted = weight_girr_vega_sensitivity_batch(
        batch,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert len(weighted) == len(sensitivities)
    assert [item.sensitivity_id for item in weighted] == [
        "vega-001",
        "vega-002",
        "vega-003",
    ]
    assert [item.qualifier for item in weighted] == ["5y", "1y", "1y"]
    assert all(item.factor_key == () for item in weighted)


def test_girr_vega_batch_rejects_context_scope_mismatch() -> None:
    batch = build_sbm_batch(sample_vega_sensitivities(), SbmRiskClass.GIRR, SbmRiskMeasure.VEGA)
    context = replace(sample_context(), desk_id="different-desk")

    with pytest.raises(ValueError, match="desk_id"):
        calculate_sbm_capital_from_batch(batch, context=context)


def test_girr_vega_arrow_batch_rejects_missing_option_tenor() -> None:
    table = sample_vega_arrow_table(sample_vega_sensitivities()).drop(["option_tenor"])

    with pytest.raises(ValueError, match="option_tenor"):
        normalize_sbm_path(SbmRiskClass.GIRR, SbmRiskMeasure.VEGA, table)


def test_girr_vega_handoff_builder_does_not_construct_row_dataclasses() -> None:
    import frtb_sbm.arrow_batch as arrow_batch

    source = inspect.getsource(arrow_batch)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source


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
