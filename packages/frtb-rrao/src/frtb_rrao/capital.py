"""
RRAO line add-ons and deterministic explain subtotals.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for capital.py, Basel MAR23.8,
    U.S. NPR 2.0 proposed section __.211(c), and EU Article 325u(3).
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_rrao.classification import classify_rrao_positions
from frtb_rrao.data_models import (
    RraoCapitalLine,
    RraoClassification,
    RraoClassificationDecision,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSubtotal,
)
from frtb_rrao.reference_data import risk_weight_rule_for
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

_SUBTOTAL_TYPE_ORDER = ("classification", "evidence_type", "desk_id", "legal_entity")


def build_rrao_capital_lines(
    positions: object,
    *,
    profile: RraoRegulatoryProfile | str = RraoRegulatoryProfile.US_NPR_2_0,
) -> tuple[RraoCapitalLine, ...]:
    """Build additive line add-ons for supported canonical RRAO positions."""

    validated = validate_rrao_positions(positions)
    decisions = classify_rrao_positions(validated, profile=profile)
    if len(validated) != len(decisions):
        raise RraoInputError("classification decision count does not match positions")

    return tuple(
        _capital_line_for_position(position, decision, profile=profile)
        for position, decision in zip(validated, decisions, strict=True)
    )


def build_rrao_subtotals(lines: Iterable[RraoCapitalLine]) -> tuple[RraoSubtotal, ...]:
    """Build deterministic explain subtotals by classification, evidence, desk, and entity."""

    materialised = tuple(lines)
    subtotal_maps: dict[str, dict[str, list[RraoCapitalLine]]] = {
        subtotal_type: {} for subtotal_type in _SUBTOTAL_TYPE_ORDER
    }

    for line in materialised:
        _append_subtotal_line(subtotal_maps["classification"], line.classification.value, line)
        _append_subtotal_line(subtotal_maps["evidence_type"], line.evidence_type.value, line)
        _append_subtotal_line(subtotal_maps["desk_id"], line.desk_id, line)
        _append_subtotal_line(subtotal_maps["legal_entity"], line.legal_entity, line)

    subtotals: list[RraoSubtotal] = []
    for subtotal_type in _SUBTOTAL_TYPE_ORDER:
        for subtotal_key in sorted(subtotal_maps[subtotal_type]):
            grouped_lines = subtotal_maps[subtotal_type][subtotal_key]
            subtotals.append(
                RraoSubtotal(
                    subtotal_key=subtotal_key,
                    subtotal_type=subtotal_type,
                    gross_effective_notional=sum(
                        line.gross_effective_notional for line in grouped_lines
                    ),
                    add_on=sum(line.add_on for line in grouped_lines),
                    position_ids=tuple(line.position_id for line in grouped_lines),
                )
            )
    return tuple(subtotals)


def included_rrao_total(lines: Iterable[RraoCapitalLine]) -> float:
    """Return the additive RRAO total for included lines."""

    return sum(line.add_on for line in lines if not line.is_excluded)


def _capital_line_for_position(
    position: RraoPosition,
    decision: RraoClassificationDecision,
    *,
    profile: RraoRegulatoryProfile | str,
) -> RraoCapitalLine:
    risk_weight_rule = risk_weight_rule_for(profile, decision.risk_weight_key)
    if risk_weight_rule.classification is not decision.classification:
        raise RraoInputError(
            "risk-weight classification does not match decision",
            field="risk_weight_key",
            position_id=position.position_id,
        )

    add_on = position.gross_effective_notional * risk_weight_rule.risk_weight
    is_excluded = decision.classification is RraoClassification.EXCLUDED
    return RraoCapitalLine(
        position_id=position.position_id,
        classification=decision.classification,
        evidence_type=decision.evidence_type,
        gross_effective_notional=position.gross_effective_notional,
        risk_weight=risk_weight_rule.risk_weight,
        add_on=add_on,
        currency=position.currency,
        is_excluded=is_excluded,
        reason_code=decision.reason_code,
        citations=_merged_citation_ids(decision.citations, (risk_weight_rule.citation_id,)),
        desk_id=position.desk_id,
        legal_entity=position.legal_entity,
        source_row_id=position.source_row_id,
        exclusion_reason=decision.exclusion_reason,
        exclusion_evidence_id=decision.exclusion_evidence_id,
    )


def _append_subtotal_line(
    subtotal_map: dict[str, list[RraoCapitalLine]],
    subtotal_key: str,
    line: RraoCapitalLine,
) -> None:
    subtotal_map.setdefault(subtotal_key, []).append(line)


def _merged_citation_ids(*citation_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in citation_groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


__all__ = [
    "build_rrao_capital_lines",
    "build_rrao_subtotals",
    "included_rrao_total",
]
