"""Shared test-only helpers for SBM fixture loaders."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    WeightedSensitivity,
)

SbmInvalidCase = tuple[str, str, tuple[SbmSensitivity, ...]]
SbmSensitivityFactory = Callable[[Mapping[str, Any]], SbmSensitivity]


def load_sbm_fixture_context(payload: dict[str, Any]) -> SbmCalculationContext:
    if "context" not in payload:
        raise ValueError("Missing 'context' key in payload")
    context = payload["context"]
    for key in (
        "run_id",
        "calculation_date",
        "base_currency",
        "reporting_currency",
        "profile_id",
    ):
        if key not in context:
            raise ValueError(f"Missing '{key}' key in context payload")

    return SbmCalculationContext(
        run_id=str(context["run_id"]),
        calculation_date=date.fromisoformat(str(context["calculation_date"])),
        base_currency=str(context["base_currency"]),
        reporting_currency=str(context["reporting_currency"]),
        profile_id=str(context["profile_id"]),
    )


def load_sbm_invalid_cases(
    payload: Iterable[Mapping[str, Any]],
    sensitivity_factory: SbmSensitivityFactory,
) -> tuple[SbmInvalidCase, ...]:
    cases: list[SbmInvalidCase] = []
    for case in payload:
        sensitivities = [sensitivity_factory(case["sensitivity"])]
        if "duplicate_of" in case:
            sensitivities.append(sensitivity_factory(case["duplicate_of"]))
        cases.append(
            (
                str(case["case_id"]),
                str(case["expected_error_match"]),
                tuple(sensitivities),
            )
        )
    return tuple(cases)


def sbm_sensitivity_from_payload(
    payload: Mapping[str, Any],
    *,
    text_fields: Sequence[str],
    int_fields: Sequence[str] = (),
    float_fields: Sequence[str] = (),
) -> SbmSensitivity:
    source_row_id = str(payload["source_row_id"])
    column_map: list[tuple[str, str]] = [("amount", "amount")]
    optional_fields: dict[str, object] = {}
    for field in text_fields:
        if field in payload:
            optional_fields[field] = str(payload[field])
            column_map.append((field, field))
    for field in int_fields:
        if field in payload:
            optional_fields[field] = int(payload[field])
    for field in float_fields:
        if field in payload:
            optional_fields[field] = float(payload[field])
    return SbmSensitivity(
        sensitivity_id=str(payload["sensitivity_id"]),
        source_row_id=source_row_id,
        desk_id=str(payload["desk_id"]),
        legal_entity=str(payload["legal_entity"]),
        risk_class=SbmRiskClass(str(payload["risk_class"])),
        risk_measure=SbmRiskMeasure(str(payload["risk_measure"])),
        bucket=str(payload["bucket"]),
        risk_factor=str(payload["risk_factor"]),
        amount=float(payload["amount"]),
        amount_currency=str(payload["amount_currency"]),
        sign_convention=SbmSignConvention(str(payload["sign_convention"])),
        lineage=SbmSourceLineage(
            source_system="synthetic-sbm-fixture",
            source_file="sensitivities.json",
            source_row_id=source_row_id,
            source_column_map=tuple(column_map),
        ),
        mapping_citation_ids=tuple(payload.get("mapping_citation_ids", ())),
        **optional_fields,
    )


DEFAULT_SBM_SOURCE_COLUMN_MAP = (
    ("RiskType", "risk_class"),
    ("AmountUSD", "amount"),
)


def sample_sbm_lineage(
    row_id: str = "row-001",
    *,
    source_file: str = "sbm.csv",
    source_column_map: tuple[tuple[str, str], ...] = DEFAULT_SBM_SOURCE_COLUMN_MAP,
) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file=source_file,
        source_row_id=row_id,
        source_column_map=source_column_map,
    )


def sample_sbm_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "sens-001",
        "source_row_id": "row-001",
        "desk_id": "rates-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.GIRR,
        "risk_measure": SbmRiskMeasure.DELTA,
        "bucket": "1",
        "risk_factor": "USD",
        "amount": 1_000_000.0,
        "amount_currency": "USD",
        "tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_sbm_lineage(),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def sample_sbm_context(**overrides: object) -> SbmCalculationContext:
    fields = {
        "run_id": "run-001",
        "calculation_date": date(2026, 5, 30),
        "base_currency": "USD",
        "reporting_currency": "USD",
        "profile_id": SbmRegulatoryProfile.US_NPR_2_0.value,
    }
    fields.update(overrides)
    return SbmCalculationContext(**fields)  # type: ignore[arg-type]


def sample_sbm_basel_context(run_id: str) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_sbm_weighted_sensitivity(
    *,
    sensitivity_id: str,
    scaled_amount: float,
    bucket: str = "USD",
) -> WeightedSensitivity:
    return WeightedSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        raw_amount=scaled_amount,
        risk_weight=1.0,
        scaled_amount=scaled_amount,
        citation_ids=("basel_mar21_girr",),
    )
