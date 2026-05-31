from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from frtb_cva import (
    BaCvaHedgeType,
    CvaCalculationContext,
    CvaHedge,
    CvaMethod,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)

FIXTURE_DIR = Path(__file__).parent


def load_fixture_payload() -> dict[str, Any]:
    return _load_json("inputs.json")


def load_expected_outputs() -> dict[str, Any]:
    return _load_json("expected_outputs.json")


def load_fixture_context() -> CvaCalculationContext:
    context = load_fixture_payload()["context"]
    return CvaCalculationContext(
        run_id=str(context["run_id"]),
        calculation_date=date.fromisoformat(str(context["calculation_date"])),
        base_currency=str(context["base_currency"]),
        profile=CvaRegulatoryProfile(str(context["profile"])),
        method=CvaMethod(str(context["method"])),
        sa_cva_approved=bool(context["sa_cva_approved"]),
    )


SaCvaFixtureCase = tuple[
    str,
    tuple[SaCvaSensitivity, ...],
    tuple[CvaHedge, ...],
]
InvalidSaCvaFixtureCase = tuple[
    str,
    str,
    tuple[SaCvaSensitivity, ...],
    tuple[CvaHedge, ...],
]


def load_fixture_cases() -> tuple[SaCvaFixtureCase, ...]:
    payload = load_fixture_payload()
    return tuple(
        (
            str(case["case_id"]),
            tuple(_sensitivity_from_payload(item) for item in case["sensitivities"]),
            tuple(_hedge_from_payload(item) for item in case.get("hedges", [])),
        )
        for case in payload["cases"]
    )


def load_invalid_cases() -> tuple[InvalidSaCvaFixtureCase, ...]:
    payload = load_fixture_payload()
    return tuple(
        (
            str(case["case_id"]),
            str(case["expected_error_match"]),
            tuple(_sensitivity_from_payload(item) for item in case["sensitivities"]),
            tuple(_hedge_from_payload(item) for item in case.get("hedges", [])),
        )
        for case in payload["invalid_cases"]
    )


def _sensitivity_from_payload(payload: dict[str, Any]) -> SaCvaSensitivity:
    source_row_id = str(payload["source_row_id"])
    hedge_id = payload.get("hedge_id")
    return SaCvaSensitivity(
        sensitivity_id=str(payload["sensitivity_id"]),
        risk_class=SaCvaRiskClass(str(payload["risk_class"])),
        risk_measure=SaCvaRiskMeasure(str(payload["risk_measure"])),
        sensitivity_tag=SensitivityTag(str(payload["sensitivity_tag"])),
        bucket_id=str(payload["bucket_id"]),
        risk_factor_key=str(payload["risk_factor_key"]),
        tenor=payload.get("tenor"),
        amount=float(payload["amount"]),
        amount_currency=str(payload["amount_currency"]),
        sign_convention=str(payload["sign_convention"]),
        source_row_id=source_row_id,
        hedge_id=str(hedge_id) if hedge_id is not None else None,
        lineage=_lineage(source_row_id),
    )


def _hedge_from_payload(payload: dict[str, Any]) -> CvaHedge:
    source_row_id = str(payload["source_row_id"])
    return CvaHedge(
        hedge_id=str(payload["hedge_id"]),
        source_row_id=source_row_id,
        counterparty_id=str(payload["counterparty_id"]),
        hedge_type=BaCvaHedgeType(str(payload["hedge_type"])),
        notional=float(payload["notional"]),
        remaining_maturity=float(payload["remaining_maturity"]),
        discount_factor=float(payload["discount_factor"]),
        reference_sector=CvaSector(str(payload["reference_sector"])),
        reference_region=str(payload["reference_region"]),
        reference_relation=HedgeReferenceRelation(str(payload["reference_relation"])),
        eligibility=HedgeEligibility(str(payload["eligibility"])),
        is_internal=bool(payload["is_internal"]),
        eligibility_evidence_id=str(payload["eligibility_evidence_id"])
        if payload.get("eligibility_evidence_id") is not None
        else None,
        lineage=_lineage(source_row_id),
    )


def _lineage(source_row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva-fixture",
        source_file="inputs.json",
        source_row_id=source_row_id,
        source_column_map=(("amount", "amount"),),
    )


def _load_json(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)
