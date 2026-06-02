"""
RRAO line add-ons and deterministic explain subtotals.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for capital.py, Basel MAR23.8,
    U.S. NPR 2.0 proposed section __.211(c), and EU Article 325u(3).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from frtb_rrao._citations import merged_citation_ids
from frtb_rrao.classification import _classify_validated_rrao_positions
from frtb_rrao.data_models import (
    RraoCapitalLine,
    RraoClassification,
    RraoClassificationDecision,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSubtotal,
)
from frtb_rrao.reference_data import risk_weight_rule_for
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

_SUBTOTAL_TYPE_ORDER = ("classification", "evidence_type", "desk_id", "legal_entity")


@dataclass
class _SubtotalAccumulator:
    gross_effective_notional: float = 0.0
    add_on: float = 0.0
    position_ids: list[str] = field(default_factory=list)


def build_rrao_capital_lines(
    positions: object,
    *,
    profile: RraoRegulatoryProfile | str = RraoRegulatoryProfile.US_NPR_2_0,
) -> tuple[RraoCapitalLine, ...]:
    """Build additive line add-ons for supported canonical RRAO positions."""

    rule_profile = get_rrao_rule_profile(profile)
    validated = validate_rrao_positions(positions)
    return _build_rrao_capital_lines_from_validated(validated, profile=rule_profile.profile)


def _build_rrao_capital_lines_from_validated(
    positions: tuple[RraoPosition, ...],
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[RraoCapitalLine, ...]:
    """Build line add-ons from an already validated tuple of RRAO positions."""

    decisions = _classify_validated_rrao_positions(positions, profile=profile)
    if len(positions) != len(decisions):
        raise RraoInputError("classification decision count does not match positions")

    return tuple(
        _capital_line_for_position(position, decision, profile=profile)
        for position, decision in zip(positions, decisions, strict=True)
    )


def build_rrao_subtotals(lines: Iterable[RraoCapitalLine]) -> tuple[RraoSubtotal, ...]:
    """Build deterministic explain subtotals by classification, evidence, desk, and entity."""

    materialised = tuple(lines)
    subtotal_maps: dict[str, dict[str, _SubtotalAccumulator]] = {
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
                    gross_effective_notional=grouped_lines.gross_effective_notional,
                    add_on=grouped_lines.add_on,
                    position_ids=tuple(grouped_lines.position_ids),
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
        citations=merged_citation_ids(decision.citations, (risk_weight_rule.citation_id,)),
        desk_id=position.desk_id,
        legal_entity=position.legal_entity,
        source_row_id=position.source_row_id,
        exclusion_reason=decision.exclusion_reason,
        exclusion_evidence_id=decision.exclusion_evidence_id,
    )


def _append_subtotal_line(
    subtotal_map: dict[str, _SubtotalAccumulator],
    subtotal_key: str,
    line: RraoCapitalLine,
) -> None:
    accumulator = subtotal_map.setdefault(subtotal_key, _SubtotalAccumulator())
    accumulator.gross_effective_notional += line.gross_effective_notional
    accumulator.add_on += line.add_on
    accumulator.position_ids.append(line.position_id)


__all__ = [
    "build_rrao_capital_lines",
    "build_rrao_subtotals",
    "included_rrao_total",
]
