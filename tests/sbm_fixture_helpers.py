"""Shared test-only helpers for SBM fixture loaders."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from frtb_sbm import (
    SbmCalculationContext,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
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
