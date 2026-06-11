"""RRAO classification and exclusion decisions.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for classification.py, Basel
    MAR23.2-MAR23.7, U.S. NPR 2.0 proposed section __.211(a)-__.211(b),
    and Delegated Regulation (EU) 2022/2328 Articles 1-3.
"""

from __future__ import annotations

from typing import Any, cast

from frtb_rrao._citations import merged_citation_ids
from frtb_rrao.data_models import (
    RraoClassification,
    RraoClassificationDecision,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
)
from frtb_rrao.kernel.classification import RraoDecisionArrays, decision_arrays_for_batch
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation import validate_rrao_positions


def classify_rrao_positions(
    positions: object,
    *,
    profile: RraoRegulatoryProfile | str = RraoRegulatoryProfile.US_NPR_2_0,
) -> tuple[RraoClassificationDecision, ...]:
    """Classify validated RRAO positions for a supported rule profile.
    Parameters
    ----------
    positions : object
        Positions.
    profile : RraoRegulatoryProfile | str, optional
        Profile.

    Returns
    -------
    tuple[RraoClassificationDecision, ...]
        Result of the operation.
    """

    rule_profile = get_rrao_rule_profile(profile)
    validated = validate_rrao_positions(positions)
    if not validated:
        return ()
    return _classify_validated_rrao_positions(validated, profile=rule_profile.profile)


def _classify_validated_rrao_positions(
    positions: tuple[RraoPosition, ...],
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[RraoClassificationDecision, ...]:
    if not positions:
        return ()
    from frtb_rrao.batch import build_rrao_batch_from_positions

    batch = build_rrao_batch_from_positions(positions)
    decisions = decision_arrays_for_batch(batch, profile=profile)
    return tuple(
        _classification_decision_from_batch(batch, decisions, index=index)
        for index in range(batch.row_count)
    )


def classify_rrao_position(
    position: RraoPosition,
    *,
    profile: RraoRegulatoryProfile | str = RraoRegulatoryProfile.US_NPR_2_0,
) -> RraoClassificationDecision:
    """Classify one canonical RRAO position for a supported rule profile.
    Parameters
    ----------
    position : RraoPosition
        Position.
    profile : RraoRegulatoryProfile | str, optional
        Profile.

    Returns
    -------
    RraoClassificationDecision
        Result of the operation.
    """

    return classify_rrao_positions((position,), profile=profile)[0]


def _classification_decision_from_batch(
    batch: Any,
    decisions: RraoDecisionArrays,
    *,
    index: int,
) -> RraoClassificationDecision:
    return RraoClassificationDecision(
        position_id=cast(str, batch.position_ids[index]),
        classification=RraoClassification(cast(str, decisions.classifications[index])),
        evidence_type=RraoEvidenceType(cast(str, batch.evidence_types[index])),
        reason_code=cast(str, decisions.reason_codes[index]),
        risk_weight_key=cast(str, decisions.risk_weight_keys[index]),
        citations=merged_citation_ids(decisions.decision_citations[index], batch.citations[index]),
        exclusion_reason=(
            None
            if batch.exclusion_reasons[index] is None
            else RraoExclusionReason(cast(str, batch.exclusion_reasons[index]))
        ),
        exclusion_evidence_id=cast(str | None, batch.exclusion_evidence_ids[index]),
        supervisor_directive_id=cast(str | None, batch.supervisor_directive_ids[index]),
    )


__all__ = [
    "classify_rrao_position",
    "classify_rrao_positions",
]
