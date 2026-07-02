"""Shared test-only helpers for RRAO fixtures and data models."""

from __future__ import annotations

from collections.abc import Callable

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoSourceLineage,
)

RRAO_SOURCE_COLUMN_MAP = (
    ("RiskType", "evidence_type"),
    ("AmountUSD", "gross_effective_notional"),
)


def sample_rrao_lineage(
    row_id: str = "row-001",
    *,
    source_file: str = "rrao.csv",
    source_column_map: tuple[tuple[str, str], ...] = RRAO_SOURCE_COLUMN_MAP,
) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file=source_file,
        source_row_id=row_id,
        source_column_map=source_column_map,
    )


def sample_rrao_position(**overrides: object) -> RraoPosition:
    fields = {
        "position_id": "pos-001",
        "source_row_id": "row-001",
        "desk_id": "rates-exotics",
        "legal_entity": "LE-001",
        "gross_effective_notional": 1_000_000.0,
        "currency": "USD",
        "evidence_type": RraoEvidenceType.EXOTIC_UNDERLYING,
        "evidence_label": "weather derivative",
        "classification_hint": RraoClassification.EXOTIC,
        "lineage": sample_rrao_lineage(),
    }
    fields.update(overrides)
    return RraoPosition(**fields)  # type: ignore[arg-type]


def rrao_position_from_payload(
    payload: object,
    *,
    lineage_factory: Callable[[str], RraoSourceLineage] = sample_rrao_lineage,
) -> RraoPosition:
    assert isinstance(payload, dict)
    exclusion_reason = payload.get("exclusion_reason")
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
        classification_hint=RraoClassification(str(payload["classification_hint"])),
        exclusion_reason=(
            RraoExclusionReason(str(exclusion_reason)) if exclusion_reason is not None else None
        ),
        exclusion_evidence_id=optional_rrao_text(payload.get("exclusion_evidence_id")),
        back_to_back_match=optional_rrao_back_to_back_match(payload.get("back_to_back_match")),
        lineage=lineage_factory(source_row_id),
    )


def optional_rrao_back_to_back_match(value: object) -> RraoBackToBackMatch | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"expected back-to-back match object, got {value!r}")
    match_group_id = str(value["match_group_id"])
    matched_position_id = str(value["matched_position_id"])
    return RraoBackToBackMatch(
        match_group_id=match_group_id,
        matched_position_id=matched_position_id,
    )


def optional_rrao_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
