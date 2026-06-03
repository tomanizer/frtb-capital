"""Validation helpers for upstream securitisation and CTP risk-weight evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from frtb_drc._validation_utils import (
    require_finite_non_negative as _require_finite_non_negative,
)
from frtb_drc._validation_utils import (
    require_text as _require_text,
)
from frtb_drc.data_models import (
    DrcCalculationContext,
    DrcPosition,
    DrcRiskClass,
    DrcRiskWeightEvidence,
)
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID, get_rule_profile
from frtb_drc.validation import DrcInputError


def risk_weight_evidence_by_position(
    evidence: Iterable[DrcRiskWeightEvidence],
    *,
    field_name: str = "risk_weight_evidence",
) -> dict[str, DrcRiskWeightEvidence]:
    """Return evidence keyed by position id, rejecting duplicate records."""

    result: dict[str, DrcRiskWeightEvidence] = {}
    for record in evidence:
        position_id = _require_text(record.position_id, f"{field_name}.position_id")
        if position_id in result:
            raise DrcInputError(
                f"{field_name} contains duplicate risk-weight evidence for {position_id}"
            )
        result[position_id] = record
    return result


def validate_risk_weight_evidence(
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> None:
    """Validate all evidence records for one DRC risk class in a context."""

    field_name, evidence = _context_evidence(context, risk_class=risk_class)
    for position_id, record in evidence.items():
        _validate_evidence_record(
            record,
            position_id=position_id,
            field_name=field_name,
            risk_class=risk_class,
            context=context,
        )


def effective_risk_weights(
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> dict[str, float]:
    """Combine legacy float maps with typed evidence into one validated map."""

    raw_field_name, raw_weights = _context_raw_weights(context, risk_class=risk_class)
    evidence_field_name, evidence = _context_evidence(context, risk_class=risk_class)
    result: dict[str, float] = {}
    if raw_weights and context.profile_id != US_NPR_2_0_PROFILE_ID:
        raise DrcInputError(
            f"{raw_field_name} legacy float maps are only supported for "
            f"{US_NPR_2_0_PROFILE_ID}; provide typed risk-weight evidence for "
            f"profile {context.profile_id}"
        )
    for position_id, risk_weight in raw_weights.items():
        key = _require_text(position_id, f"{raw_field_name} position_id")
        result[key] = _require_finite_non_negative(
            risk_weight,
            f"{raw_field_name}[{key!r}]",
        )
    for position_id, record in evidence.items():
        key = _require_text(position_id, f"{evidence_field_name} position_id")
        _validate_evidence_record(
            record,
            position_id=key,
            field_name=evidence_field_name,
            risk_class=risk_class,
            context=context,
        )
        evidence_weight = record.effective_risk_weight
        if key in result and result[key] != evidence_weight:
            raise DrcInputError(
                f"{raw_field_name}[{key!r}] conflicts with {evidence_field_name}[{key!r}]"
            )
        result[key] = evidence_weight
    return result


def used_risk_weight_evidence(
    positions: Iterable[DrcPosition],
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> tuple[DrcRiskWeightEvidence, ...]:
    """Return typed evidence records used by the supplied positions."""

    _field_name, evidence = _context_evidence(context, risk_class=risk_class)
    position_ids = tuple(
        sorted(
            position.position_id
            for position in positions
            if DrcRiskClass(position.risk_class) == risk_class and position.position_id in evidence
        )
    )
    return tuple(evidence[position_id] for position_id in position_ids)


def used_risk_weight_evidence_for_position_ids(
    position_ids: Iterable[str],
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> tuple[DrcRiskWeightEvidence, ...]:
    """Return typed evidence records used by a columnar batch."""

    _field_name, evidence = _context_evidence(context, risk_class=risk_class)
    return tuple(
        evidence[position_id]
        for position_id in sorted(set(position_ids))
        if position_id in evidence
    )


def risk_weight_evidence_hash_payload(
    position_ids: Iterable[str],
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> tuple[dict[str, object], ...]:
    """Return stable JSON-ready evidence payload for hashing."""

    return tuple(
        record.as_dict()
        for record in used_risk_weight_evidence_for_position_ids(
            position_ids,
            context,
            risk_class=risk_class,
        )
    )


def _validate_evidence_record(
    record: DrcRiskWeightEvidence,
    *,
    position_id: str,
    field_name: str,
    risk_class: DrcRiskClass,
    context: DrcCalculationContext,
) -> None:
    if record.position_id != position_id:
        raise DrcInputError(f"{field_name}[{position_id!r}] position_id must match its context key")
    if DrcRiskClass(record.risk_class) != risk_class:
        raise DrcInputError(f"{field_name}[{position_id!r}] has wrong risk_class")
    _require_text(record.source_profile_id, f"{field_name}[{position_id!r}].source_profile_id")
    if record.source_profile_id != context.profile_id:
        raise DrcInputError(
            f"{field_name}[{position_id!r}].source_profile_id "
            f"{record.source_profile_id!r} does not match context profile_id "
            f"{context.profile_id!r}"
        )
    _require_text(record.source_table, f"{field_name}[{position_id!r}].source_table")
    _require_text(record.source_method, f"{field_name}[{position_id!r}].source_method")
    _require_text(record.source_id, f"{field_name}[{position_id!r}].source_id")
    _validate_lineage(record, field_name=f"{field_name}[{position_id!r}].lineage")
    if record.as_of_date > context.calculation_date:
        raise DrcInputError(
            f"{field_name}[{position_id!r}].as_of_date must not be after calculation_date"
        )
    if record.is_stale or "STALE" in record.validation_flags:
        raise DrcInputError(f"{field_name}[{position_id!r}] is stale")
    _require_finite_non_negative(
        record.effective_risk_weight,
        f"{field_name}[{position_id!r}].effective_risk_weight",
    )
    if not record.citation_ids:
        raise DrcInputError(f"{field_name}[{position_id!r}].citation_ids must be non-empty")
    profile_citations = set(get_rule_profile(context.profile_id).citations)
    for citation_id in record.citation_ids:
        citation = _require_text(citation_id, f"{field_name}[{position_id!r}].citation_ids")
        if citation not in profile_citations:
            raise DrcInputError(
                f"{field_name}[{position_id!r}].citation_ids contains citation "
                f"{citation!r} outside profile {context.profile_id}"
            )


def _validate_lineage(record: DrcRiskWeightEvidence, *, field_name: str) -> None:
    lineage = record.lineage
    if lineage is None:
        raise DrcInputError(f"{field_name} must be provided")
    _require_text(lineage.source_system, f"{field_name}.source_system")
    _require_text(lineage.source_file, f"{field_name}.source_file")
    _require_text(lineage.source_row_id, f"{field_name}.source_row_id")


def _context_raw_weights(
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> tuple[str, Mapping[str, float]]:
    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return (
            "context.securitisation_non_ctp_risk_weights",
            context.securitisation_non_ctp_risk_weights,
        )
    if risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return "context.ctp_risk_weights", context.ctp_risk_weights
    raise DrcInputError(f"risk-weight evidence is not supported for {risk_class.value}")


def _context_evidence(
    context: DrcCalculationContext,
    *,
    risk_class: DrcRiskClass,
) -> tuple[str, Mapping[str, DrcRiskWeightEvidence]]:
    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return (
            "context.securitisation_non_ctp_risk_weight_evidence",
            context.securitisation_non_ctp_risk_weight_evidence,
        )
    if risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return "context.ctp_risk_weight_evidence", context.ctp_risk_weight_evidence
    raise DrcInputError(f"risk-weight evidence is not supported for {risk_class.value}")
