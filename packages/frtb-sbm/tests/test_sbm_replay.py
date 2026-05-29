from __future__ import annotations

import json
from datetime import date

from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    serialize_sbm_result,
)


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
    )


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-replay-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        SbmSensitivity(
            sensitivity_id="eur-1y",
            source_row_id="row-001",
            desk_id="rates-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="1",
            risk_factor="EUR",
            amount=1_000_000.0,
            amount_currency="USD",
            tenor="1y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=sample_lineage("row-001"),
        ),
        SbmSensitivity(
            sensitivity_id="usd-5y",
            source_row_id="row-002",
            desk_id="rates-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="2",
            risk_factor="USD",
            amount=800_000.0,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=sample_lineage("row-002"),
        ),
    )


def test_public_result_replay_is_deterministic() -> None:
    first = calculate_sbm_capital(sample_sensitivities(), context=sample_context())
    second = calculate_sbm_capital(sample_sensitivities(), context=sample_context())

    assert first == second
    assert first.input_hash == second.input_hash
    assert first.profile_hash == second.profile_hash
    assert serialize_sbm_result(first) == serialize_sbm_result(second)
    assert json.dumps(serialize_sbm_result(first), sort_keys=True) == json.dumps(
        serialize_sbm_result(second),
        sort_keys=True,
    )
