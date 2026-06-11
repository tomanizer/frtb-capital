"""RRAO canonical batch validation stage."""

from __future__ import annotations

from typing import Any, cast

import numpy as np

from frtb_rrao import _validation_rules as _vr
from frtb_rrao._batch_columns import _require_unique
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
)
from frtb_rrao.validation._batch_common import (
    position_id_at_first,
    require_non_empty_object_column,
    require_text_where,
)
from frtb_rrao.validation._errors import RraoInputError
from frtb_rrao.validation.investment_fund_batch import validate_investment_fund_batch_fields


def validate_rrao_batch(batch: Any) -> None:
    """Validate canonical RRAO batch invariants before kernel execution.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch.
    """

    _require_unique(batch.position_ids)
    if not np.all(np.isfinite(batch.gross_effective_notionals)):
        raise RraoInputError(
            "gross effective notional values must be finite",
            field="gross_effective_notional",
        )
    if bool(np.any(batch.gross_effective_notionals < 0.0)):
        raise RraoInputError(
            _vr.GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE,
            field="gross_effective_notional",
        )
    if bool(np.any(batch.classification_hints == RraoClassification.UNSUPPORTED.value)):
        raise RraoInputError(
            _vr.UNSUPPORTED_CLASSIFICATION_MESSAGE,
            field="classification_hint",
            position_id=position_id_at_first(
                batch,
                batch.classification_hints == RraoClassification.UNSUPPORTED.value,
            ),
        )
    if bool(np.any(~batch.lineage_present)):
        raise RraoInputError(
            _vr.SOURCE_LINEAGE_REQUIRED_MESSAGE,
            field="lineage",
            position_id=position_id_at_first(batch, ~batch.lineage_present),
        )
    require_non_empty_object_column(
        batch,
        batch.lineage_source_systems,
        field="lineage.source_system",
    )
    require_non_empty_object_column(
        batch,
        batch.lineage_source_files,
        field="lineage.source_file",
    )
    require_non_empty_object_column(
        batch,
        batch.lineage_source_row_ids,
        field="lineage.source_row_id",
    )
    _validate_evidence_requirements(batch)
    _validate_back_to_back_match_groups(batch)
    validate_investment_fund_batch_fields(batch)


def _validate_evidence_requirements(batch: Any) -> None:
    supervisor_mask = (batch.evidence_types == RraoEvidenceType.SUPERVISOR_DIRECTIVE.value) | (
        batch.classification_hints == RraoClassification.SUPERVISOR_DIRECTED.value
    )
    require_text_where(
        batch,
        batch.supervisor_directive_ids,
        supervisor_mask,
        field="supervisor_directive_id",
    )

    excluded_hint_mask = batch.classification_hints == RraoClassification.EXCLUDED.value
    missing_exclusion_reason = excluded_hint_mask & (batch.exclusion_reasons == None)  # noqa: E711
    if bool(np.any(missing_exclusion_reason)):
        raise RraoInputError(
            _vr.EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE,
            field="exclusion_reason",
            position_id=position_id_at_first(batch, missing_exclusion_reason),
        )

    has_exclusion_reason = batch.exclusion_reasons != None  # noqa: E711
    wrong_exclusion_evidence = has_exclusion_reason & (
        batch.evidence_types != RraoEvidenceType.EXPLICIT_EXCLUSION.value
    )
    if bool(np.any(wrong_exclusion_evidence)):
        raise RraoInputError(
            _vr.EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE,
            field="evidence_type",
            position_id=position_id_at_first(batch, wrong_exclusion_evidence),
        )
    require_text_where(
        batch,
        batch.exclusion_evidence_ids,
        has_exclusion_reason,
        field="exclusion_evidence_id",
    )

    explicit_exclusion = batch.evidence_types == RraoEvidenceType.EXPLICIT_EXCLUSION.value
    missing_reason_for_explicit = explicit_exclusion & (batch.exclusion_reasons == None)  # noqa: E711
    if bool(np.any(missing_reason_for_explicit)):
        raise RraoInputError(
            _vr.EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE,
            field="exclusion_reason",
            position_id=position_id_at_first(batch, missing_reason_for_explicit),
        )
    require_text_where(
        batch,
        batch.exclusion_evidence_ids,
        explicit_exclusion,
        field="exclusion_evidence_id",
    )

    exact_back_to_back = (
        batch.exclusion_reasons == RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK.value
    )
    match_present = (batch.back_to_back_match_group_ids != None) | (  # noqa: E711
        batch.back_to_back_matched_position_ids != None  # noqa: E711
    )
    missing_match = exact_back_to_back & ~match_present
    if bool(np.any(missing_match)):
        raise RraoInputError(
            _vr.EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE,
            field="back_to_back_match",
            position_id=position_id_at_first(batch, missing_match),
        )
    invalid_match_context = match_present & ~exact_back_to_back
    if bool(np.any(invalid_match_context)):
        raise RraoInputError(
            _vr.BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE,
            field="back_to_back_match",
            position_id=position_id_at_first(batch, invalid_match_context),
        )
    require_text_where(
        batch,
        batch.back_to_back_match_group_ids,
        match_present,
        field="back_to_back_match.match_group_id",
    )
    require_text_where(
        batch,
        batch.back_to_back_matched_position_ids,
        match_present,
        field="back_to_back_match.matched_position_id",
    )


def _validate_back_to_back_match_groups(batch: Any) -> None:
    match_mask = batch.back_to_back_match_group_ids != None  # noqa: E711
    if not bool(np.any(match_mask)):
        return

    match_indices = np.nonzero(match_mask)[0]
    self_matches = (
        batch.back_to_back_matched_position_ids[match_indices] == batch.position_ids[match_indices]
    )
    if bool(np.any(self_matches)):
        index = int(match_indices[np.nonzero(self_matches)[0][0]])
        raise RraoInputError(
            _vr.BACK_TO_BACK_SELF_MATCH_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=cast(str, batch.position_ids[index]),
        )

    missing_matches = ~np.isin(
        batch.back_to_back_matched_position_ids[match_indices],
        batch.position_ids,
    )
    if bool(np.any(missing_matches)):
        index = int(match_indices[np.nonzero(missing_matches)[0][0]])
        raise RraoInputError(
            _vr.BACK_TO_BACK_MISSING_MATCH_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=cast(str, batch.position_ids[index]),
        )

    positions_by_id = {
        cast(str, batch.position_ids[int(index)]): int(index) for index in match_indices
    }
    match_groups: dict[str, list[int]] = {}
    for raw_index in match_indices:
        index = int(raw_index)
        match_group_id = batch.back_to_back_match_group_ids[index]
        matched_position_id = cast(str, batch.back_to_back_matched_position_ids[index])
        if matched_position_id not in positions_by_id:
            raise RraoInputError(
                _vr.BACK_TO_BACK_REQUIRES_EVIDENCED_COUNTERPART_MESSAGE,
                field="back_to_back_match.matched_position_id",
                position_id=cast(str, batch.position_ids[index]),
            )
        match_groups.setdefault(cast(str, match_group_id), []).append(index)

    for match_group_id in sorted(match_groups):
        indices = match_groups[match_group_id]
        if len(indices) != 2:
            joined = ", ".join(cast(str, batch.position_ids[index]) for index in indices)
            raise RraoInputError(
                f"exact back-to-back match group must contain exactly two transactions: {joined}",
                field="back_to_back_match.match_group_id",
                position_id=cast(str, batch.position_ids[indices[0]]),
            )
        left, right = indices
        _validate_exact_back_to_back_pair(batch, left, right)


def _validate_exact_back_to_back_pair(
    batch: Any,
    left: int,
    right: int,
) -> None:
    left_id = cast(str, batch.position_ids[left])
    right_id = cast(str, batch.position_ids[right])
    if batch.back_to_back_matched_position_ids[left] != right_id:
        raise RraoInputError(
            _vr.BACK_TO_BACK_CROSS_REFERENCE_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=left_id,
        )
    if batch.back_to_back_matched_position_ids[right] != left_id:
        raise RraoInputError(
            _vr.BACK_TO_BACK_CROSS_REFERENCE_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=right_id,
        )
    if batch.exclusion_evidence_ids[left] != batch.exclusion_evidence_ids[right]:
        raise RraoInputError(
            _vr.BACK_TO_BACK_SHARED_EVIDENCE_MESSAGE,
            field="exclusion_evidence_id",
            position_id=right_id,
        )
    if batch.currencies[left] != batch.currencies[right]:
        raise RraoInputError(
            _vr.BACK_TO_BACK_MATCHING_CURRENCY_MESSAGE,
            field="currency",
            position_id=right_id,
        )
    if not np.isclose(
        float(batch.gross_effective_notionals[left]),
        float(batch.gross_effective_notionals[right]),
        rtol=_vr.NOTIONAL_RECONCILIATION_REL_TOL,
        atol=_vr.NOTIONAL_RECONCILIATION_ABS_TOL,
    ):
        raise RraoInputError(
            _vr.BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE,
            field="gross_effective_notional",
            position_id=right_id,
        )


__all__ = ["position_id_at_first", "validate_rrao_batch"]
