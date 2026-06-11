"""Nested RRAO payload component builders."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, cast

from frtb_rrao.data_models import (
    RraoBackToBackMatch,
    RraoInvestmentFundDescriptor,
    RraoSourceLineage,
)


def lineage_payload(lineage: RraoSourceLineage | None) -> dict[str, object] | None:
    """
    Return the deterministic payload for a source-lineage object.

    Parameters
    ----------
    lineage : RraoSourceLineage | None
        Source-lineage record.

    Returns
    -------
    dict[str, object] | None
        JSON-stable lineage payload, or ``None``.
    """
    if lineage is None:
        return None
    return lineage_payload_from_values(
        source_system=lineage.source_system,
        source_file=lineage.source_file,
        source_row_id=lineage.source_row_id,
        source_column_map=lineage.source_column_map,
    )


def lineage_payload_from_values(
    *,
    source_system: object,
    source_file: object,
    source_row_id: object,
    source_column_map: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    """
    Return the deterministic payload for source-lineage scalar values.

    Parameters
    ----------
    source_system, source_file, source_row_id, source_column_map : object
        Source-lineage scalar values.

    Returns
    -------
    dict[str, object]
        JSON-stable lineage payload.
    """
    return {
        "source_system": source_system,
        "source_file": source_file,
        "source_row_id": source_row_id,
        "source_column_map": [list(pair) for pair in source_column_map],
    }


def investment_fund_descriptor_payload(
    descriptor: RraoInvestmentFundDescriptor | None,
) -> dict[str, object] | None:
    """
    Return the deterministic payload for an investment-fund descriptor.

    Parameters
    ----------
    descriptor : RraoInvestmentFundDescriptor | None
        Investment-fund descriptor.

    Returns
    -------
    dict[str, object] | None
        JSON-stable descriptor payload, or ``None``.
    """
    if descriptor is None:
        return None
    return investment_fund_descriptor_payload_from_values(
        is_investment_fund_exposure=True,
        fund_id=descriptor.fund_id,
        section_205_method=descriptor.section_205_method,
        included_exposure_type=descriptor.included_exposure_type,
        mandate_evidence_id=descriptor.mandate_evidence_id,
        section_205_evidence_id=descriptor.section_205_evidence_id,
        fund_gross_effective_notional=descriptor.fund_gross_effective_notional,
        included_exposure_ratio=descriptor.included_exposure_ratio,
        look_through_available=descriptor.look_through_available,
        mandate_allows_rrao_exposures=descriptor.mandate_allows_rrao_exposures,
    )


def investment_fund_descriptor_payload_from_values(
    *,
    is_investment_fund_exposure: bool,
    fund_id: object,
    section_205_method: object,
    included_exposure_type: object,
    mandate_evidence_id: object,
    section_205_evidence_id: object,
    fund_gross_effective_notional: object,
    included_exposure_ratio: object,
    look_through_available: object,
    mandate_allows_rrao_exposures: object,
) -> dict[str, object] | None:
    """
    Return the deterministic payload for investment-fund scalar values.

    Parameters
    ----------
    is_investment_fund_exposure, fund_id, section_205_method, included_exposure_type,
    mandate_evidence_id, section_205_evidence_id, fund_gross_effective_notional,
    included_exposure_ratio, look_through_available, mandate_allows_rrao_exposures : object
        Investment-fund scalar values.

    Returns
    -------
    dict[str, object] | None
        JSON-stable descriptor payload, or ``None``.
    """
    if not is_investment_fund_exposure:
        return None
    return {
        "fund_id": fund_id,
        "section_205_method": enum_or_value(section_205_method),
        "included_exposure_type": enum_or_value(included_exposure_type),
        "mandate_evidence_id": mandate_evidence_id,
        "section_205_evidence_id": section_205_evidence_id,
        "fund_gross_effective_notional": float_value(fund_gross_effective_notional),
        "included_exposure_ratio": float_value(included_exposure_ratio),
        "look_through_available": bool(look_through_available),
        "mandate_allows_rrao_exposures": bool(mandate_allows_rrao_exposures),
    }


def back_to_back_match_payload(match: RraoBackToBackMatch | None) -> dict[str, object] | None:
    """
    Return the deterministic payload for a back-to-back match object.

    Parameters
    ----------
    match : RraoBackToBackMatch | None
        Back-to-back match record.

    Returns
    -------
    dict[str, object] | None
        JSON-stable match payload, or ``None``.
    """
    if match is None:
        return None
    return back_to_back_match_payload_from_values(
        match_group_id=match.match_group_id,
        matched_position_id=match.matched_position_id,
    )


def back_to_back_match_payload_from_values(
    *,
    match_group_id: object,
    matched_position_id: object,
) -> dict[str, object] | None:
    """
    Return the deterministic payload for back-to-back match scalar values.

    Parameters
    ----------
    match_group_id, matched_position_id : object
        Back-to-back match scalar values.

    Returns
    -------
    dict[str, object] | None
        JSON-stable match payload, or ``None``.
    """
    if match_group_id is None:
        return None
    return {
        "match_group_id": match_group_id,
        "matched_position_id": matched_position_id,
    }


def enum_or_value(value: object) -> object:
    """
    Return the value for string enums and the original object otherwise.

    Parameters
    ----------
    value : object
        Candidate enum value.

    Returns
    -------
    object
        Enum wire value or original object.
    """
    if isinstance(value, StrEnum):
        return value.value
    return value


def float_value(value: object) -> float:
    """
    Return an object coerced through the package-standard float path.

    Parameters
    ----------
    value : object
        Numeric value.

    Returns
    -------
    float
        Float value for deterministic payload serialization.
    """
    return float(cast(Any, value))
