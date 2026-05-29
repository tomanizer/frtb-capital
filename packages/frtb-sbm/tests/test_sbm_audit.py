from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date

import pytest
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    input_hash_for_sensitivities,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
)
from frtb_sbm import audit as audit_module


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
    )


def sample_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    bucket: str = "1",
    risk_factor: str = "EUR",
    tenor: str = "1y",
    amount: float = 1_000_000.0,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        tenor=tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(source_row_id),
    )


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-run-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def test_input_hash_is_deterministic_and_input_sensitive() -> None:
    sensitivities = (
        sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),
        sample_sensitivity(sensitivity_id="sens-002", source_row_id="row-002"),
    )
    same_sensitivities = (
        sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),
        sample_sensitivity(sensitivity_id="sens-002", source_row_id="row-002"),
    )
    reordered = tuple(reversed(sensitivities))

    digest = input_hash_for_sensitivities(sensitivities)

    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == input_hash_for_sensitivities(same_sensitivities)
    assert digest != input_hash_for_sensitivities(reordered)


def test_result_serialization_is_json_stable() -> None:
    result = calculate_sbm_capital(
        (sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),),
        context=sample_context(),
    )
    payload = serialize_sbm_result(result)

    assert payload == result.as_dict()
    assert json.dumps(payload, sort_keys=True)
    assert payload["profile_id"] == "BASEL_MAR21"
    assert payload["risk_classes"][0]["risk_class"] == "GIRR"


def test_reconciliation_rejects_wrong_total() -> None:
    result = calculate_sbm_capital(
        (sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),),
        context=sample_context(),
    )
    corrupted = replace(result, total_capital=0.0)

    with pytest.raises(SbmInputError, match="total capital does not reconcile"):
        validate_sbm_result_reconciliation(corrupted)


def test_reconciliation_rejects_invalid_result_hashes() -> None:
    result = calculate_sbm_capital(
        (sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),),
        context=sample_context(),
    )

    with pytest.raises(SbmInputError, match="hash must be a sha256 hex digest"):
        validate_sbm_result_reconciliation(replace(result, profile_hash="short"))
    with pytest.raises(SbmInputError, match="hash must be a sha256 hex digest"):
        validate_sbm_result_reconciliation(replace(result, input_hash="z" * 64))


def test_reconciliation_rejects_wrong_selected_scenario_total() -> None:
    result = calculate_sbm_capital(
        (sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),),
        context=sample_context(),
    )
    girr = result.risk_classes[0]
    corrupted_girr = replace(
        girr,
        selected_capital=girr.selected_capital + 1.0,
    )
    corrupted = replace(
        result,
        risk_classes=(corrupted_girr,),
        total_capital=corrupted_girr.selected_capital,
    )

    with pytest.raises(SbmInputError, match="selected risk-class capital does not reconcile"):
        validate_sbm_result_reconciliation(corrupted)


def test_reconciliation_rejects_missing_scenario_metadata() -> None:
    result = calculate_sbm_capital(
        (sample_sensitivity(sensitivity_id="sens-001", source_row_id="row-001"),),
        context=sample_context(),
    )
    girr = replace(
        result.risk_classes[0],
        scenario_totals=None,
        selected_scenario=SbmScenarioLabel.MEDIUM,
    )
    corrupted = replace(
        result,
        risk_classes=(girr,),
        total_capital=girr.selected_capital,
    )

    with pytest.raises(SbmInputError, match="scenario totals and selected scenario"):
        validate_sbm_result_reconciliation(corrupted)


def test_audit_normalisation_helpers_are_json_ready() -> None:
    payload = {
        "enum": SbmRiskMeasure.DELTA,
        "date": date(2026, 5, 30),
        "items": (SbmRiskClass.GIRR,),
    }

    assert audit_module._normalise(payload) == {
        "date": "2026-05-30",
        "enum": "DELTA",
        "items": ["GIRR"],
    }
