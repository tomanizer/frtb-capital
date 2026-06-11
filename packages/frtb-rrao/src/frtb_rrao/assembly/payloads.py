"""RRAO audit payload assembly stage."""

from __future__ import annotations

from frtb_rrao.assembly._hashing import hash_payload, hash_position_payloads
from frtb_rrao.assembly._payload_components import (
    back_to_back_match_payload,
    back_to_back_match_payload_from_values,
    enum_or_value,
    float_value,
    investment_fund_descriptor_payload,
    investment_fund_descriptor_payload_from_values,
    lineage_payload,
    lineage_payload_from_values,
)
from frtb_rrao.data_models import RraoPosition

_BatchIdentityValues = tuple[object, object, object, object, object, object, object, object]
_BatchLineageValues = tuple[object, object, object, tuple[tuple[str, str], ...]]
_BatchClassificationValues = tuple[object, object, object, object]
_BatchShapeValues = tuple[object, object, object, object, object, object]
_BatchFundValues = tuple[
    object, object, object, object, object, object, object, object, object, object
]
_BatchAuditValues = tuple[object, tuple[str, ...], object, object]


def position_payload(position: RraoPosition) -> dict[str, object]:
    """
    Return the deterministic audit payload for a canonical position.

    Parameters
    ----------
    position : RraoPosition
        Canonical RRAO position.

    Returns
    -------
    dict[str, object]
        JSON-stable position payload.
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
    """
    Return the deterministic audit payload for a batch position row.

    Parameters
    ----------
    **values : object
        Scalar values from the canonical batch row.

    Returns
    -------
    dict[str, object]
        JSON-stable position payload.
    """
    # fmt: off
    return _batch_position_payload_from_groups(
        identity=(position_id, source_row_id, desk_id, legal_entity,
                  gross_effective_notional, currency, evidence_type, evidence_label),
        lineage=(lineage_source_system, lineage_source_file, lineage_source_row_id,
                 source_column_map),
        classification=(classification_hint, exclusion_reason, exclusion_evidence_id,
                        supervisor_directive_id),
        shape=(underlying_count, is_path_dependent, has_maturity, has_strike_or_barrier,
               has_multiple_strikes_or_barriers, is_ctp_hedge),
        fund=(
            is_investment_fund_exposure, investment_fund_id, investment_fund_section_205_method,
            investment_fund_included_exposure_type, investment_fund_mandate_evidence_id,
            investment_fund_section_205_evidence_id, investment_fund_gross_effective_notional,
            investment_fund_included_exposure_ratio, investment_fund_look_through_available,
            investment_fund_mandate_allows_rrao_exposures,
        ),
        audit=(notional_source, citations, back_to_back_match_group_id,
               back_to_back_matched_position_id),
    )
    # fmt: on


def _batch_position_payload_from_groups(
    *,
    identity: _BatchIdentityValues,
    lineage: _BatchLineageValues,
    classification: _BatchClassificationValues,
    shape: _BatchShapeValues,
    fund: _BatchFundValues,
    audit: _BatchAuditValues,
) -> dict[str, object]:
    (
        position_id,
        source_row_id,
        desk_id,
        legal_entity,
        gross_effective_notional,
        currency,
        evidence_type,
        evidence_label,
    ) = identity
    lineage_source_system, lineage_source_file, lineage_source_row_id, source_column_map = lineage
    classification_hint, exclusion_reason, exclusion_evidence_id, supervisor_directive_id = (
        classification
    )
    (
        underlying_count,
        is_path_dependent,
        has_maturity,
        has_strike_or_barrier,
        has_multiple_strikes_or_barriers,
        is_ctp_hedge,
    ) = shape
    is_investment_fund_exposure = fund[0]
    notional_source, citations, _, _ = audit
    return position_payload_from_values(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        gross_effective_notional=float_value(gross_effective_notional),
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
        investment_fund_descriptor=_batch_fund_payload(fund),
        notional_source=notional_source,
        citations=citations,
        back_to_back_match=_batch_match_payload(audit),
    )


def _batch_fund_payload(fund: _BatchFundValues) -> dict[str, object] | None:
    (
        is_investment_fund_exposure,
        investment_fund_id,
        investment_fund_section_205_method,
        investment_fund_included_exposure_type,
        investment_fund_mandate_evidence_id,
        investment_fund_section_205_evidence_id,
        investment_fund_gross_effective_notional,
        investment_fund_included_exposure_ratio,
        investment_fund_look_through_available,
        investment_fund_mandate_allows_rrao_exposures,
    ) = fund
    return investment_fund_descriptor_payload_from_values(
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
    )


def _batch_match_payload(audit: _BatchAuditValues) -> dict[str, object] | None:
    _, _, back_to_back_match_group_id, back_to_back_matched_position_id = audit
    return back_to_back_match_payload_from_values(
        match_group_id=back_to_back_match_group_id,
        matched_position_id=back_to_back_matched_position_id,
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
    """
    Return the shared position payload shape used by row and batch hashes.

    Parameters
    ----------
    **values : object
        Normalized scalar and nested payload values.

    Returns
    -------
    dict[str, object]
        JSON-stable position payload.
    """
    payload: dict[str, object] = {
        "position_id": position_id,
        "source_row_id": source_row_id,
        "desk_id": desk_id,
        "legal_entity": legal_entity,
        "gross_effective_notional": gross_effective_notional,
        "currency": currency,
        "evidence_type": enum_or_value(evidence_type),
        "evidence_label": evidence_label,
        "lineage": lineage,
        "classification_hint": enum_or_value(classification_hint),
        "exclusion_reason": enum_or_value(exclusion_reason),
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


__all__ = [
    "batch_position_payload",
    "hash_payload",
    "hash_position_payloads",
    "position_payload",
]
