from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from frtb_sbm import (
    SbmCalculationContext,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)

FIXTURE_DIR = Path(__file__).parent


def load_fixture_context() -> SbmCalculationContext:
    payload = _load_json("sensitivities.json")
    context = payload["context"]
    return SbmCalculationContext(
        run_id=str(context["run_id"]),
        calculation_date=date.fromisoformat(str(context["calculation_date"])),
        base_currency=str(context["base_currency"]),
        reporting_currency=str(context["reporting_currency"]),
        profile_id=str(context["profile_id"]),
    )


def load_fixture_sensitivities() -> tuple[SbmSensitivity, ...]:
    payload = _load_json("sensitivities.json")
    return tuple(_sensitivity_from_payload(sensitivity) for sensitivity in payload["sensitivities"])


def load_expected_outputs() -> dict[str, object]:
    return _load_json("expected_outputs.json")


def load_invalid_cases() -> tuple[tuple[str, str, tuple[SbmSensitivity, ...]], ...]:
    payload = _load_json("invalid_cases.json")
    cases: list[tuple[str, str, tuple[SbmSensitivity, ...]]] = []
    for case in payload:
        sensitivities = [_sensitivity_from_payload(case["sensitivity"])]
        if "duplicate_of" in case:
            sensitivities.append(_sensitivity_from_payload(case["duplicate_of"]))
        cases.append(
            (
                str(case["case_id"]),
                str(case["expected_error_match"]),
                tuple(sensitivities),
            )
        )
    return tuple(cases)


def _sensitivity_from_payload(payload: dict[str, Any]) -> SbmSensitivity:
    source_row_id = str(payload["source_row_id"])
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
        tenor=str(payload["tenor"]),
        sign_convention=SbmSignConvention(str(payload["sign_convention"])),
        lineage=SbmSourceLineage(
            source_system="synthetic-sbm-fixture",
            source_file="sensitivities.json",
            source_row_id=source_row_id,
            source_column_map=(("amount", "amount"), ("tenor", "tenor")),
        ),
        mapping_citation_ids=tuple(payload.get("mapping_citation_ids", ())),
    )


def _load_json(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)
