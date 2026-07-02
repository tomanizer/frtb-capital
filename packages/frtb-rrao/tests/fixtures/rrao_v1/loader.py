from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
)
from tests.rrao_fixture_helpers import optional_rrao_back_to_back_match

FIXTURE_DIR = Path(__file__).parent


def load_fixture_context() -> RraoCalculationContext:
    payload = _load_json("positions.json")
    context = payload["context"]
    return RraoCalculationContext(
        run_id=str(context["run_id"]),
        calculation_date=date.fromisoformat(str(context["calculation_date"])),
        base_currency=str(context["base_currency"]),
        profile=RraoRegulatoryProfile(str(context["profile"])),
    )


def load_fixture_positions() -> tuple[RraoPosition, ...]:
    payload = _load_json("positions.json")
    return tuple(_position_from_payload(position) for position in payload["positions"])


def load_expected_outputs() -> dict[str, object]:
    return _load_json("expected_outputs.json")


def load_invalid_cases() -> tuple[tuple[str, str, RraoPosition], ...]:
    payload = _load_json("invalid_cases.json")
    return tuple(
        (
            str(case["case_id"]),
            str(case["expected_error_match"]),
            _position_from_payload(case["position"]),
        )
        for case in payload
    )


def _position_from_payload(payload: dict[str, Any]) -> RraoPosition:
    source_row_id = str(payload["source_row_id"])
    return RraoPosition(
        position_id=str(payload["position_id"]),
        source_row_id=source_row_id,
        desk_id=str(payload["desk_id"]),
        legal_entity=str(payload["legal_entity"]),
        gross_effective_notional=float(payload["gross_effective_notional"]),
        currency=str(payload["currency"]),
        evidence_type=RraoEvidenceType(str(payload["evidence_type"])),
        evidence_label=str(payload["evidence_label"]),
        lineage=RraoSourceLineage(
            source_system="synthetic-rrao-fixture",
            source_file="positions.json",
            source_row_id=source_row_id,
            source_column_map=(
                ("evidence_type", "evidence_type"),
                ("gross_effective_notional", "gross_effective_notional"),
            ),
        ),
        classification_hint=_optional_classification(payload.get("classification_hint")),
        exclusion_reason=_optional_exclusion_reason(payload.get("exclusion_reason")),
        exclusion_evidence_id=_optional_text(payload.get("exclusion_evidence_id")),
        back_to_back_match=optional_rrao_back_to_back_match(payload.get("back_to_back_match")),
        supervisor_directive_id=_optional_text(payload.get("supervisor_directive_id")),
        underlying_count=_optional_int(payload.get("underlying_count")),
        is_path_dependent=_optional_bool(payload.get("is_path_dependent")),
    )


def _optional_classification(value: object) -> RraoClassification | None:
    if value is None:
        return None
    return RraoClassification(str(value))


def _optional_exclusion_reason(value: object) -> RraoExclusionReason | None:
    if value is None:
        return None
    return RraoExclusionReason(str(value))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError(f"expected bool fixture value, got {value!r}")
    return value


def _load_json(filename: str) -> Any:
    return json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
