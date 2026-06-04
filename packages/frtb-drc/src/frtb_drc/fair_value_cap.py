"""Validation helpers for securitisation non-CTP fair-value cap evidence."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError, jsonable

from frtb_drc._validation_utils import require_text as _require_text
from frtb_drc.data_models import (
    DrcCalculationContext,
    DrcFairValueCapEvidence,
    DrcPosition,
)
from frtb_drc.regimes import get_rule_profile
from frtb_drc.validation import DrcInputError


def fair_value_cap_evidence_by_position(
    records: Iterable[DrcFairValueCapEvidence],
    *,
    field_name: str = "fair_value_cap_evidence",
) -> dict[str, DrcFairValueCapEvidence]:
    """Return fair-value cap evidence keyed by position id, rejecting duplicates.
    Parameters
    ----------
    records : Iterable[DrcFairValueCapEvidence]
        Records.
    field_name : str, optional
        Human-readable field label for error messages.

    Returns
    -------
    dict[str, DrcFairValueCapEvidence]
        Result of the operation.
    """

    by_position: dict[str, DrcFairValueCapEvidence] = {}
    for record in records:
        _require_text(record.position_id, f"{field_name}.position_id")
        if record.position_id in by_position:
            raise DrcInputError(f"duplicate fair-value cap evidence for {record.position_id}")
        by_position[record.position_id] = record
    return by_position


def validate_fair_value_cap_evidence(
    evidence: Mapping[str, DrcFairValueCapEvidence],
    *,
    context: DrcCalculationContext,
) -> None:
    """Validate run-scoped fair-value cap evidence without requiring positions.
    Parameters
    ----------
    evidence : Mapping[str, DrcFairValueCapEvidence]
        Risk-weight or fair-value-cap evidence records.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.
    """

    if not evidence:
        return
    profile = get_rule_profile(context.profile_id)
    if not profile.securitisation_non_ctp_fair_value_cap_allowed:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-drc does not support securitisation non-CTP fair-value cap "
            f"for profile {profile.profile_id}"
        )

    for position_id, record in evidence.items():
        _require_text(position_id, "securitisation_non_ctp_fair_value_cap_evidence position_id")
        if position_id != record.position_id:
            raise DrcInputError(
                "context.securitisation_non_ctp_fair_value_cap_evidence key "
                f"{position_id!r} does not match record position_id {record.position_id!r}"
            )
        _validate_record(record, context=context)


def used_fair_value_cap_evidence(
    positions: Iterable[DrcPosition],
    context: DrcCalculationContext,
) -> tuple[DrcFairValueCapEvidence, ...]:
    """Return cap evidence used by supplied positions in deterministic order.
    Parameters
    ----------
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    tuple[DrcFairValueCapEvidence, ...]
        Result of the operation.
    """

    position_ids = tuple(sorted(position.position_id for position in positions))
    return used_fair_value_cap_evidence_for_position_ids(position_ids, context)


def used_fair_value_cap_evidence_for_position_ids(
    position_ids: Iterable[str],
    context: DrcCalculationContext,
) -> tuple[DrcFairValueCapEvidence, ...]:
    """Return cap evidence used by supplied position ids in deterministic order.
    Parameters
    ----------
    position_ids : Iterable[str]
        Position identifiers to filter evidence.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    tuple[DrcFairValueCapEvidence, ...]
        Result of the operation.
    """

    evidence = context.securitisation_non_ctp_fair_value_cap_evidence
    return tuple(
        evidence[position_id] for position_id in sorted(position_ids) if position_id in evidence
    )


def fair_value_cap_hash_payload(
    position_ids: Iterable[str],
    context: DrcCalculationContext,
) -> tuple[dict[str, object], ...]:
    """Return deterministic JSON-ready cap evidence payload for input hashes.
    Parameters
    ----------
    position_ids : Iterable[str]
        Position identifiers to filter evidence.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    tuple[dict[str, object], ...]
        Result of the operation.
    """

    return tuple(
        cast(dict[str, object], jsonable(record.as_dict()))
        for record in used_fair_value_cap_evidence_for_position_ids(position_ids, context)
    )


def _validate_record(
    record: DrcFairValueCapEvidence,
    *,
    context: DrcCalculationContext,
) -> None:
    field_prefix = f"fair_value_cap_evidence[{record.position_id}]"
    _require_text(record.position_id, "fair_value_cap_evidence.position_id")
    _require_text(record.source_profile_id, f"{field_prefix}.source_profile_id")
    if record.source_profile_id != context.profile_id:
        raise DrcInputError(
            f"{field_prefix}.source_profile_id "
            f"{record.source_profile_id!r} does not match context profile_id "
            f"{context.profile_id!r}"
        )
    _require_text(record.eligibility_reason, f"{field_prefix}.eligibility_reason")
    _require_text(record.source_id, f"{field_prefix}.source_id")
    if record.lineage is None:
        raise DrcInputError(f"{field_prefix}.lineage is required")
    _require_text(record.lineage.source_system, f"{field_prefix}.lineage.source_system")
    _require_text(record.lineage.source_file, f"{field_prefix}.lineage.source_file")
    _require_text(record.lineage.source_row_id, f"{field_prefix}.lineage.source_row_id")
    if not record.citation_ids:
        raise DrcInputError(f"{field_prefix}.citation_ids must be non-empty")
    if record.is_stale or "STALE" in {flag.strip().upper() for flag in record.validation_flags}:
        raise DrcInputError(f"{field_prefix} is stale")
    if record.as_of_date is None:
        raise DrcInputError(f"{field_prefix}.as_of_date is required")
    if record.as_of_date > context.calculation_date:
        raise DrcInputError(f"{field_prefix}.as_of_date is after calculation_date")
    if record.eligible is None:
        raise DrcInputError(f"{field_prefix}.eligible is required")
    if record.eligible:
        if record.fair_value_cap_amount is None:
            raise DrcInputError(f"{field_prefix}.fair_value_cap_amount is required")
        if not math.isfinite(record.fair_value_cap_amount) or record.fair_value_cap_amount < 0.0:
            raise DrcInputError(
                f"{field_prefix}.fair_value_cap_amount must be finite and non-negative"
            )
    elif record.fair_value_cap_amount is not None:
        raise DrcInputError(f"{field_prefix} is ineligible but supplies fair_value_cap_amount")


__all__ = [
    "fair_value_cap_evidence_by_position",
    "fair_value_cap_hash_payload",
    "used_fair_value_cap_evidence",
    "used_fair_value_cap_evidence_for_position_ids",
    "validate_fair_value_cap_evidence",
]
