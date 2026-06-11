"""
RRAO line add-ons and deterministic explain subtotals.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for capital.py, Basel MAR23.8,
    U.S. NPR 2.0 proposed section __.211(c), and EU Article 325u(3).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from frtb_rrao.data_models import (
    RraoCapitalLine,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSubtotal,
)
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation import validate_rrao_positions

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
    """Build additive line add-ons for supported canonical RRAO positions.
    Parameters
    ----------
    positions : object
        Positions.
    profile : RraoRegulatoryProfile | str, optional
        Profile.

    Returns
    -------
    tuple[RraoCapitalLine, ...]
        Result of the operation.
    """

    rule_profile = get_rrao_rule_profile(profile)
    validated = validate_rrao_positions(positions)
    return _batch_capital_lines_from_validated(validated, profile=rule_profile.profile)


def _batch_capital_lines_from_validated(
    positions: tuple[RraoPosition, ...],
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[RraoCapitalLine, ...]:
    """Build line add-ons from the canonical batch capital kernel."""

    if not positions:
        return ()
    from frtb_rrao.batch import _capital_lines_from_batch, build_rrao_batch_from_positions

    batch = build_rrao_batch_from_positions(positions)
    lines, _, _, _ = _capital_lines_from_batch(batch, profile=profile)
    return lines


def build_rrao_subtotals(lines: Iterable[RraoCapitalLine]) -> tuple[RraoSubtotal, ...]:
    """Build deterministic explain subtotals by classification, evidence, desk, and entity.
    Parameters
    ----------
    lines : Iterable[RraoCapitalLine]
        Lines.

    Returns
    -------
    tuple[RraoSubtotal, ...]
        Result of the operation.
    """

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
    """Return the additive RRAO total for included lines.
    Parameters
    ----------
    lines : Iterable[RraoCapitalLine]
        Lines.

    Returns
    -------
    float
        Result of the operation.
    """

    return sum(line.add_on for line in lines if not line.is_excluded)


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
