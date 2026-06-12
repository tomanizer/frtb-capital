"""Vectorized RRAO batch classification kernel stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
import numpy.typing as npt

from frtb_rrao._batch_columns import ObjectArray
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoRegulatoryProfile,
)
from frtb_rrao.reference_data import (
    evidence_rules_for_profile,
    exclusion_rules_for_profile,
    investment_fund_rules_for_profile,
)
from frtb_rrao.validation import RraoInputError


@dataclass(frozen=True)
class RraoDecisionArrays:
    """Vectorized classification decisions before risk-weight lookup."""

    classifications: ObjectArray
    risk_weight_keys: ObjectArray
    reason_codes: ObjectArray
    decision_citations: tuple[tuple[str, ...], ...]


@dataclass
class _DecisionState:
    classifications: ObjectArray
    risk_weight_keys: ObjectArray
    reason_codes: ObjectArray
    citation_groups: list[tuple[str, ...]]
    assigned: npt.NDArray[np.bool_]
    hint_check_mask: npt.NDArray[np.bool_]


def decision_arrays_for_batch(
    batch: Any,
    *,
    profile: RraoRegulatoryProfile,
) -> RraoDecisionArrays:
    """Classify a canonical RRAO batch into vectorized decision arrays.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch with NumPy-backed column arrays.
    profile : RraoRegulatoryProfile
        Regulatory profile used to select evidence, exclusion, and
        investment-fund rule tables.

    Returns
    -------
    RraoDecisionArrays
        Read-only classification, risk-weight key, reason-code, and citation
        arrays for downstream capital-line assembly.
    """

    state = _empty_decision_state(batch.row_count)
    _apply_exclusion_decisions(batch, state, profile=profile)
    _apply_investment_fund_decisions(batch, state, profile=profile)
    _apply_evidence_decisions(batch, state, profile=profile)
    _validate_hint_compatibility(
        batch,
        state.classifications,
        mask=state.hint_check_mask,
    )
    return RraoDecisionArrays(
        classifications=_batch_arrays.object_array(state.classifications, copy=False),
        risk_weight_keys=_batch_arrays.object_array(state.risk_weight_keys, copy=False),
        reason_codes=_batch_arrays.object_array(state.reason_codes, copy=False),
        decision_citations=tuple(state.citation_groups),
    )


def _empty_decision_state(row_count: int) -> _DecisionState:
    return _DecisionState(
        classifications=np.empty(row_count, dtype=object),
        risk_weight_keys=np.empty(row_count, dtype=object),
        reason_codes=np.empty(row_count, dtype=object),
        citation_groups=[() for _ in range(row_count)],
        assigned=np.zeros(row_count, dtype=np.bool_),
        hint_check_mask=np.zeros(row_count, dtype=np.bool_),
    )


def _apply_exclusion_decisions(
    batch: Any,
    state: _DecisionState,
    *,
    profile: RraoRegulatoryProfile,
) -> None:
    exclusion_mask = _exclusion_path_mask(batch)
    if not bool(np.any(exclusion_mask)):
        return
    exclusion_assigned = np.zeros(batch.row_count, dtype=np.bool_)
    for exclusion_rule in exclusion_rules_for_profile(profile):
        mask = exclusion_mask & (batch.exclusion_reasons == exclusion_rule.exclusion_reason.value)
        _assign_decision_mask(
            mask,
            state=state,
            classification=RraoClassification.EXCLUDED,
            risk_weight_key=exclusion_rule.risk_weight_key,
            reason_code=exclusion_rule.reason_code,
            citation_ids=(exclusion_rule.citation_id,),
        )
        exclusion_assigned |= mask
    unsupported_exclusions = exclusion_mask & ~exclusion_assigned
    if bool(np.any(unsupported_exclusions)):
        index = int(np.nonzero(unsupported_exclusions)[0][0])
        raise RraoInputError(
            f"no RRAO exclusion rule for {batch.exclusion_reasons[index]}",
            field="exclusion_reason",
            position_id=cast(str, batch.position_ids[index]),
        )
    state.assigned |= exclusion_assigned


def _apply_investment_fund_decisions(
    batch: Any,
    state: _DecisionState,
    *,
    profile: RraoRegulatoryProfile,
) -> None:
    fund_mask = (~state.assigned) & (
        batch.evidence_types == RraoEvidenceType.INVESTMENT_FUND_EXPOSURE.value
    )
    if not bool(np.any(fund_mask)):
        return
    fund_assigned = np.zeros(batch.row_count, dtype=np.bool_)
    for fund_rule in investment_fund_rules_for_profile(profile):
        mask = fund_mask & (
            batch.investment_fund_included_exposure_types == fund_rule.included_exposure_type.value
        )
        _assign_decision_mask(
            mask,
            state=state,
            classification=fund_rule.classification,
            risk_weight_key=fund_rule.risk_weight_key,
            reason_code=fund_rule.reason_code,
            citation_ids=fund_rule.citation_ids,
        )
        fund_assigned |= mask
    unsupported_funds = fund_mask & ~fund_assigned
    if bool(np.any(unsupported_funds)):
        index = int(np.nonzero(unsupported_funds)[0][0])
        raise RraoInputError(
            (
                "no RRAO investment-fund rule for "
                f"{batch.investment_fund_included_exposure_types[index]}"
            ),
            field="investment_fund_descriptor.included_exposure_type",
            position_id=cast(str, batch.position_ids[index]),
        )
    state.assigned |= fund_assigned
    state.hint_check_mask |= fund_assigned


def _apply_evidence_decisions(
    batch: Any,
    state: _DecisionState,
    *,
    profile: RraoRegulatoryProfile,
) -> None:
    evidence_mask = ~state.assigned
    if not bool(np.any(evidence_mask)):
        return
    evidence_assigned = np.zeros(batch.row_count, dtype=np.bool_)
    for evidence_rule in evidence_rules_for_profile(profile):
        mask = evidence_mask & (batch.evidence_types == evidence_rule.evidence_type.value)
        _assign_decision_mask(
            mask,
            state=state,
            classification=evidence_rule.classification,
            risk_weight_key=evidence_rule.risk_weight_key,
            reason_code=evidence_rule.reason_code,
            citation_ids=(evidence_rule.citation_id,),
        )
        evidence_assigned |= mask
    unsupported_evidence = evidence_mask & ~evidence_assigned
    if bool(np.any(unsupported_evidence)):
        index = int(np.nonzero(unsupported_evidence)[0][0])
        raise RraoInputError(
            f"no RRAO evidence rule for {batch.evidence_types[index]}",
            field="evidence_type",
            position_id=cast(str, batch.position_ids[index]),
        )
    state.assigned |= evidence_assigned
    state.hint_check_mask |= evidence_assigned


def _assign_decision_mask(
    mask: npt.NDArray[np.bool_],
    *,
    state: _DecisionState,
    classification: RraoClassification,
    risk_weight_key: str,
    reason_code: str,
    citation_ids: tuple[str, ...],
) -> None:
    if not bool(np.any(mask)):
        return
    state.classifications[mask] = classification.value
    state.risk_weight_keys[mask] = risk_weight_key
    state.reason_codes[mask] = reason_code
    for index in np.nonzero(mask)[0]:
        state.citation_groups[int(index)] = citation_ids


def _validate_hint_compatibility(
    batch: Any,
    classifications: ObjectArray,
    *,
    mask: npt.NDArray[np.bool_],
) -> None:
    has_hint = mask & (batch.classification_hints != None)  # noqa: E711
    conflicts = has_hint & (batch.classification_hints != classifications)
    if not bool(np.any(conflicts)):
        return
    index = int(np.nonzero(conflicts)[0][0])
    raise RraoInputError(
        (
            "classification hint conflicts with profile evidence rule: "
            f"{batch.classification_hints[index]} != {classifications[index]}"
        ),
        field="classification_hint",
        position_id=cast(str, batch.position_ids[index]),
    )


def _exclusion_path_mask(batch: Any) -> npt.NDArray[np.bool_]:
    return cast(
        npt.NDArray[np.bool_],
        (batch.classification_hints == RraoClassification.EXCLUDED.value)
        | (batch.exclusion_reasons != None)  # noqa: E711
        | (batch.evidence_types == RraoEvidenceType.EXPLICIT_EXCLUSION.value),
    )


__all__ = ["RraoDecisionArrays", "decision_arrays_for_batch"]
