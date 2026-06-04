"""Shared RRAO hash payload helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from enum import StrEnum
from typing import Any, cast

from frtb_common import stable_json_hash

from frtb_rrao.data_models import (
    RraoBackToBackMatch,
    RraoInvestmentFundDescriptor,
    RraoPosition,
    RraoSourceLineage,
)


def hash_payload(payload: object) -> str:
    """Return the package-standard deterministic payload hash.
    Parameters
    ----------
    payload : object
        Payload.

    Returns
    -------
    str
        Result of the operation.
    """

    return stable_json_hash(payload)


def hash_position_payloads(payloads: Iterable[dict[str, object]]) -> str:
    """Return the package-standard hash for already-normalized position payloads.
    Parameters
    ----------
    payloads : Iterable[dict[str, object]]
        Payloads.

    Returns
    -------
    str
        Result of the operation.
    """

    digest = hashlib.sha256()
    digest.update(b'{"positions":[')
    first = True
    for payload in payloads:
        if first:
            first = False
        else:
            digest.update(b",")
        digest.update(bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8"))
    digest.update(b"]}")
    return digest.hexdigest()


def position_payload(position: RraoPosition) -> dict[str, object]:
    """Return the deterministic audit payload for a canonical position.
    Parameters
    ----------
    position : RraoPosition
        Position.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """

    return position_payload_from_values(
        position_id=position.position_id,
        source_row_id=position.source_row_id,
        desk_id=position.desk_id,
        legal_entity=position.legal_entity,
        gross_effective_notional=position.gross_effective_notional,
        currency=position.currency,
        evidence_type=position.evidence_type,
        evidence_label=position.evidence_label,
        lineage=lineage_payload(position.lineage),
        classification_hint=position.classification_hint,
        exclusion_reason=position.exclusion_reason,
        exclusion_evidence_id=position.exclusion_evidence_id,
        supervisor_directive_id=position.supervisor_directive_id,
        underlying_count=position.underlying_count,
        is_path_dependent=position.is_path_dependent,
        has_maturity=position.has_maturity,
        has_strike_or_barrier=position.has_strike_or_barrier,
        has_multiple_strikes_or_barriers=position.has_multiple_strikes_or_barriers,
        is_ctp_hedge=position.is_ctp_hedge,
        is_investment_fund_exposure=position.is_investment_fund_exposure,
        investment_fund_descriptor=investment_fund_descriptor_payload(
            position.investment_fund_descriptor
        ),
        notional_source=position.notional_source,
        citations=position.citations,
        back_to_back_match=back_to_back_match_payload(position.back_to_back_match),
    )


def batch_position_payload(
    *,
    position_id: object,
    source_row_id: object,
    desk_id: object,
    legal_entity: object,
    gross_effective_notional: object,
    currency: object,
    evidence_type: object,
    evidence_label: object,
    lineage_source_system: object,
    lineage_source_file: object,
    lineage_source_row_id: object,
    source_column_map: tuple[tuple[str, str], ...],
    classification_hint: object,
    exclusion_reason: object,
    exclusion_evidence_id: object,
    supervisor_directive_id: object,
    underlying_count: object,
    is_path_dependent: object,
    has_maturity: object,
    has_strike_or_barrier: object,
    has_multiple_strikes_or_barriers: object,
    is_ctp_hedge: object,
    is_investment_fund_exposure: object,
    investment_fund_id: object,
    investment_fund_section_205_method: object,
    investment_fund_included_exposure_type: object,
    investment_fund_mandate_evidence_id: object,
    investment_fund_section_205_evidence_id: object,
    investment_fund_gross_effective_notional: object,
    investment_fund_included_exposure_ratio: object,
    investment_fund_look_through_available: object,
    investment_fund_mandate_allows_rrao_exposures: object,
    notional_source: object,
    citations: tuple[str, ...],
    back_to_back_match_group_id: object,
    back_to_back_matched_position_id: object,
) -> dict[str, object]:
    """Return the deterministic audit payload for a batch position row.
    Parameters
    ----------
    position_id : object
        Position id.
    source_row_id : object
        Source row id.
    desk_id : object
        Desk id.
    legal_entity : object
        Legal entity.
    gross_effective_notional : object
        Gross effective notional.
    currency : object
        Currency.
    evidence_type : object
        Evidence type.
    evidence_label : object
        Evidence label.
    lineage_source_system : object
        Lineage source system.
    lineage_source_file : object
        Lineage source file.
    lineage_source_row_id : object
        Lineage source row id.
    source_column_map : tuple[tuple[str, str], ...]
        Source column map.
    classification_hint : object
        Classification hint.
    exclusion_reason : object
        Exclusion reason.
    exclusion_evidence_id : object
        Exclusion evidence id.
    supervisor_directive_id : object
        Supervisor directive id.
    underlying_count : object
        Underlying count.
    is_path_dependent : object
        Is path dependent.
    has_maturity : object
        Has maturity.
    has_strike_or_barrier : object
        Has strike or barrier.
    has_multiple_strikes_or_barriers : object
        Has multiple strikes or barriers.
    is_ctp_hedge : object
        Is ctp hedge.
    is_investment_fund_exposure : object
        Is investment fund exposure.
    investment_fund_id : object
        Investment fund id.
    investment_fund_section_205_method : object
        Investment fund section 205 method.
    investment_fund_included_exposure_type : object
        Investment fund included exposure type.
    investment_fund_mandate_evidence_id : object
        Investment fund mandate evidence id.
    investment_fund_section_205_evidence_id : object
        Investment fund section 205 evidence id.
    investment_fund_gross_effective_notional : object
        Investment fund gross effective notional.
    investment_fund_included_exposure_ratio : object
        Investment fund included exposure ratio.
    investment_fund_look_through_available : object
        Investment fund look through available.
    investment_fund_mandate_allows_rrao_exposures : object
        Investment fund mandate allows rrao exposures.
    notional_source : object
        Notional source.
    citations : tuple[str, ...]
        Citations.
    back_to_back_match_group_id : object
        Back to back match group id.
    back_to_back_matched_position_id : object
        Back to back matched position id.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """

    return position_payload_from_values(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        gross_effective_notional=_float_value(gross_effective_notional),
        currency=currency,
        evidence_type=evidence_type,
        evidence_label=evidence_label,
        lineage=lineage_payload_from_values(
            source_system=lineage_source_system,
            source_file=lineage_source_file,
            source_row_id=lineage_source_row_id,
            source_column_map=source_column_map,
        ),
        classification_hint=classification_hint,
        exclusion_reason=exclusion_reason,
        exclusion_evidence_id=exclusion_evidence_id,
        supervisor_directive_id=supervisor_directive_id,
        underlying_count=underlying_count,
        is_path_dependent=is_path_dependent,
        has_maturity=has_maturity,
        has_strike_or_barrier=has_strike_or_barrier,
        has_multiple_strikes_or_barriers=has_multiple_strikes_or_barriers,
        is_ctp_hedge=bool(is_ctp_hedge),
        is_investment_fund_exposure=bool(is_investment_fund_exposure),
        investment_fund_descriptor=investment_fund_descriptor_payload_from_values(
            is_investment_fund_exposure=bool(is_investment_fund_exposure),
            fund_id=investment_fund_id,
            section_205_method=investment_fund_section_205_method,
            included_exposure_type=investment_fund_included_exposure_type,
            mandate_evidence_id=investment_fund_mandate_evidence_id,
            section_205_evidence_id=investment_fund_section_205_evidence_id,
            fund_gross_effective_notional=investment_fund_gross_effective_notional,
            included_exposure_ratio=investment_fund_included_exposure_ratio,
            look_through_available=investment_fund_look_through_available,
            mandate_allows_rrao_exposures=investment_fund_mandate_allows_rrao_exposures,
        ),
        notional_source=notional_source,
        citations=citations,
        back_to_back_match=back_to_back_match_payload_from_values(
            match_group_id=back_to_back_match_group_id,
            matched_position_id=back_to_back_matched_position_id,
        ),
    )


def position_payload_from_values(
    *,
    position_id: object,
    source_row_id: object,
    desk_id: object,
    legal_entity: object,
    gross_effective_notional: object,
    currency: object,
    evidence_type: object,
    evidence_label: object,
    lineage: dict[str, object] | None,
    classification_hint: object,
    exclusion_reason: object,
    exclusion_evidence_id: object,
    supervisor_directive_id: object,
    underlying_count: object,
    is_path_dependent: object,
    has_maturity: object,
    has_strike_or_barrier: object,
    has_multiple_strikes_or_barriers: object,
    is_ctp_hedge: object,
    is_investment_fund_exposure: object,
    investment_fund_descriptor: dict[str, object] | None,
    notional_source: object,
    citations: tuple[str, ...],
    back_to_back_match: dict[str, object] | None,
) -> dict[str, object]:
    """Return the shared position payload shape used by row and batch hashes.
    Parameters
    ----------
    position_id : object
        Position id.
    source_row_id : object
        Source row id.
    desk_id : object
        Desk id.
    legal_entity : object
        Legal entity.
    gross_effective_notional : object
        Gross effective notional.
    currency : object
        Currency.
    evidence_type : object
        Evidence type.
    evidence_label : object
        Evidence label.
    lineage : dict[str, object] | None
        Lineage.
    classification_hint : object
        Classification hint.
    exclusion_reason : object
        Exclusion reason.
    exclusion_evidence_id : object
        Exclusion evidence id.
    supervisor_directive_id : object
        Supervisor directive id.
    underlying_count : object
        Underlying count.
    is_path_dependent : object
        Is path dependent.
    has_maturity : object
        Has maturity.
    has_strike_or_barrier : object
        Has strike or barrier.
    has_multiple_strikes_or_barriers : object
        Has multiple strikes or barriers.
    is_ctp_hedge : object
        Is ctp hedge.
    is_investment_fund_exposure : object
        Is investment fund exposure.
    investment_fund_descriptor : dict[str, object] | None
        Investment fund descriptor.
    notional_source : object
        Notional source.
    citations : tuple[str, ...]
        Citations.
    back_to_back_match : dict[str, object] | None
        Back to back match.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """

    payload: dict[str, object] = {
        "position_id": position_id,
        "source_row_id": source_row_id,
        "desk_id": desk_id,
        "legal_entity": legal_entity,
        "gross_effective_notional": gross_effective_notional,
        "currency": currency,
        "evidence_type": _enum_or_value(evidence_type),
        "evidence_label": evidence_label,
        "lineage": lineage,
        "classification_hint": _enum_or_value(classification_hint),
        "exclusion_reason": _enum_or_value(exclusion_reason),
        "exclusion_evidence_id": exclusion_evidence_id,
        "supervisor_directive_id": supervisor_directive_id,
        "underlying_count": underlying_count,
        "is_path_dependent": is_path_dependent,
        "has_maturity": has_maturity,
        "has_strike_or_barrier": has_strike_or_barrier,
        "has_multiple_strikes_or_barriers": has_multiple_strikes_or_barriers,
        "is_ctp_hedge": is_ctp_hedge,
        "is_investment_fund_exposure": is_investment_fund_exposure,
        "investment_fund_descriptor": investment_fund_descriptor,
        "notional_source": notional_source,
        "citations": list(citations),
    }
    if back_to_back_match is not None:
        payload["back_to_back_match"] = back_to_back_match
    return payload


def lineage_payload(lineage: RraoSourceLineage | None) -> dict[str, object] | None:
    """Return the deterministic payload for a source-lineage object.
    Parameters
    ----------
    lineage : RraoSourceLineage | None
        Lineage.

    Returns
    -------
    dict[str, object] | None
        Result of the operation.
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
    """Return the deterministic payload for source-lineage scalar values.
    Parameters
    ----------
    source_system : object
        Source system.
    source_file : object
        Source file.
    source_row_id : object
        Source row id.
    source_column_map : tuple[tuple[str, str], ...]
        Source column map.

    Returns
    -------
    dict[str, object]
        Result of the operation.
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
    """Return the deterministic payload for an investment-fund descriptor.
    Parameters
    ----------
    descriptor : RraoInvestmentFundDescriptor | None
        Descriptor.

    Returns
    -------
    dict[str, object] | None
        Result of the operation.
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
    """Return the deterministic payload for investment-fund scalar values.
    Parameters
    ----------
    is_investment_fund_exposure : bool
        Is investment fund exposure.
    fund_id : object
        Fund id.
    section_205_method : object
        Section 205 method.
    included_exposure_type : object
        Included exposure type.
    mandate_evidence_id : object
        Mandate evidence id.
    section_205_evidence_id : object
        Section 205 evidence id.
    fund_gross_effective_notional : object
        Fund gross effective notional.
    included_exposure_ratio : object
        Included exposure ratio.
    look_through_available : object
        Look through available.
    mandate_allows_rrao_exposures : object
        Mandate allows rrao exposures.

    Returns
    -------
    dict[str, object] | None
        Result of the operation.
    """

    if not is_investment_fund_exposure:
        return None
    return {
        "fund_id": fund_id,
        "section_205_method": _enum_or_value(section_205_method),
        "included_exposure_type": _enum_or_value(included_exposure_type),
        "mandate_evidence_id": mandate_evidence_id,
        "section_205_evidence_id": section_205_evidence_id,
        "fund_gross_effective_notional": _float_value(fund_gross_effective_notional),
        "included_exposure_ratio": _float_value(included_exposure_ratio),
        "look_through_available": bool(look_through_available),
        "mandate_allows_rrao_exposures": bool(mandate_allows_rrao_exposures),
    }


def back_to_back_match_payload(match: RraoBackToBackMatch | None) -> dict[str, object] | None:
    """Return the deterministic payload for a back-to-back match object.
    Parameters
    ----------
    match : RraoBackToBackMatch | None
        Match.

    Returns
    -------
    dict[str, object] | None
        Result of the operation.
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
    """Return the deterministic payload for back-to-back match scalar values.
    Parameters
    ----------
    match_group_id : object
        Match group id.
    matched_position_id : object
        Matched position id.

    Returns
    -------
    dict[str, object] | None
        Result of the operation.
    """

    if match_group_id is None:
        return None
    return {
        "match_group_id": match_group_id,
        "matched_position_id": matched_position_id,
    }


def _enum_or_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    return value


def _float_value(value: object) -> float:
    return float(cast(Any, value))


__all__ = [
    "batch_position_payload",
    "hash_payload",
    "hash_position_payloads",
    "position_payload",
]
