from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
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
    )


FixtureCase = tuple[str, tuple[CvaCounterparty, ...], tuple[CvaNettingSet, ...]]
InvalidFixtureCase = tuple[str, str, tuple[CvaCounterparty, ...], tuple[CvaNettingSet, ...]]


def load_fixture_cases() -> tuple[FixtureCase, ...]:
    payload = load_fixture_payload()
    return tuple(
        (
            str(case["case_id"]),
            tuple(_counterparty_from_payload(item) for item in case["counterparties"]),
            tuple(_netting_set_from_payload(item) for item in case["netting_sets"]),
        )
        for case in payload["cases"]
    )


def load_invalid_cases() -> tuple[InvalidFixtureCase, ...]:
    payload = load_fixture_payload()
    return tuple(
        (
            str(case["case_id"]),
            str(case["expected_error_match"]),
            tuple(_counterparty_from_payload(item) for item in case["counterparties"]),
            tuple(_netting_set_from_payload(item) for item in case["netting_sets"]),
        )
        for case in payload["invalid_cases"]
    )


def _counterparty_from_payload(payload: dict[str, Any]) -> CvaCounterparty:
    source_row_id = str(payload["source_row_id"])
    return CvaCounterparty(
        counterparty_id=str(payload["counterparty_id"]),
        desk_id=str(payload["desk_id"]),
        legal_entity=str(payload["legal_entity"]),
        sector=CvaSector(str(payload["sector"])),
        credit_quality=CreditQuality(str(payload["credit_quality"])),
        region=str(payload["region"]),
        source_row_id=source_row_id,
        lineage=_lineage(source_row_id),
    )


def _netting_set_from_payload(payload: dict[str, Any]) -> CvaNettingSet:
    source_row_id = str(payload["source_row_id"])
    return CvaNettingSet(
        netting_set_id=str(payload["netting_set_id"]),
        counterparty_id=str(payload["counterparty_id"]),
        ead=float(payload["ead"]),
        effective_maturity=float(payload["effective_maturity"]),
        discount_factor=float(payload["discount_factor"]),
        currency=str(payload["currency"]),
        sign_convention=str(payload["sign_convention"]),
        uses_imm_ead=bool(payload["uses_imm_ead"]),
        source_row_id=source_row_id,
        lineage=_lineage(source_row_id),
    )


def _lineage(source_row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva-fixture",
        source_file="inputs.json",
        source_row_id=source_row_id,
        source_column_map=(("EAD", "ead"),),
    )


def _load_json(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)
