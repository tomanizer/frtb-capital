"""Fair-value-cap citation and branch assembly for DRC batches."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

import numpy as np

from frtb_drc._identifiers import slug_path as _slug
from frtb_drc.assembly.citations import (
    sec_non_ctp_fair_value_cap_citations,
    sec_non_ctp_gross_citations,
)
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    DrcCalculationContext,
    DrcFairValueCapEvidence,
    DrcRiskClass,
)

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch


def batch_fair_value_cap_citations(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> tuple[str, ...]:
    """Return fair-value-cap citations used by securitisation batch inputs.

    Parameters
    ----------
    batch : DrcPositionBatch
        Canonical columnar DRC position batch.
    context : DrcCalculationContext
        Run context containing securitisation fair-value-cap evidence.

    Returns
    -------
    tuple[str, ...]
        Sorted fair-value-cap citation identifiers used by the batch.
    """

    citation_ids: set[str] = set()
    for position_id in batch.position_ids:
        evidence = context.securitisation_non_ctp_fair_value_cap_evidence.get(
            cast(str, position_id)
        )
        if evidence is not None:
            citation_ids.update(sec_non_ctp_fair_value_cap_citations(context.profile_id))
            citation_ids.update(evidence.citation_ids)
    return tuple(sorted(citation_ids))


def fair_value_cap_branch_metadata_for_batch(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> tuple[BranchMetadata, ...]:
    """Return fair-value-cap branch metadata for securitisation batch runs.

    Parameters
    ----------
    batch : DrcPositionBatch
        Canonical columnar DRC position batch.
    context : DrcCalculationContext
        Run context containing securitisation fair-value-cap evidence.
    risk_class : DrcRiskClass
        Risk class represented by the batch.

    Returns
    -------
    tuple[BranchMetadata, ...]
        Branch metadata for fair-value-cap treatment.
    """

    if risk_class is not DrcRiskClass.SECURITISATION_NON_CTP:
        return ()
    evidence = context.securitisation_non_ctp_fair_value_cap_evidence
    if not evidence:
        return (_no_batch_fair_value_cap_branch(context),)
    gross_jtd = _market_value_gross_jtd_array(batch)
    return tuple(
        _fair_value_cap_branch_for_batch_row(
            batch,
            context=context,
            evidence=evidence,
            gross_jtd=gross_jtd,
            index=index,
        )
        for index in _sorted_indices(batch)
    )


def _no_batch_fair_value_cap_branch(context: DrcCalculationContext) -> BranchMetadata:
    return BranchMetadata(
        branch_id="drc-securitisation-non-ctp-batch-no-fair-value-cap",
        branch_type=BranchType.NORMAL,
        source_id=context.profile_id,
        selected=True,
        reason=(
            "batch securitisation non-CTP gross default exposure used market value; "
            "no fair-value cap evidence was supplied"
        ),
        citations=sec_non_ctp_gross_citations(context.profile_id),
    )


def _fair_value_cap_branch_for_batch_row(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    evidence: Mapping[str, DrcFairValueCapEvidence],
    gross_jtd: np.ndarray,
    index: int,
) -> BranchMetadata:
    position_id = cast(str, batch.position_ids[index])
    record = evidence.get(position_id)
    if record is None:
        return BranchMetadata(
            branch_id=f"batch-sec-non-ctp-no-fair-value-cap-{_slug(position_id)}",
            branch_type=BranchType.NORMAL,
            source_id=position_id,
            selected=True,
            reason=(
                "batch securitisation non-CTP position used market value; "
                "no fair-value cap evidence was supplied"
            ),
            citations=sec_non_ctp_gross_citations(context.profile_id),
        )
    citations = tuple(
        sorted(
            {
                *sec_non_ctp_fair_value_cap_citations(context.profile_id),
                *record.citation_ids,
            }
        )
    )
    branch_type, reason = _fair_value_cap_branch_outcome(record, gross_jtd=float(gross_jtd[index]))
    return BranchMetadata(
        branch_id=f"batch-sec-non-ctp-fair-value-cap-{_slug(position_id)}",
        branch_type=branch_type,
        source_id=record.source_id,
        selected=True,
        reason=reason,
        citations=citations,
    )


def _fair_value_cap_branch_outcome(
    record: DrcFairValueCapEvidence,
    *,
    gross_jtd: float,
) -> tuple[BranchType, str]:
    if not record.eligible:
        return (
            BranchType.NORMAL,
            (
                "batch fair-value cap evidence marked the position ineligible; "
                f"reason: {record.eligibility_reason}"
            ),
        )
    if record.fair_value_cap_amount is not None and record.fair_value_cap_amount < gross_jtd:
        return (
            BranchType.CAP,
            (
                "batch fair-value cap applied to securitisation non-CTP gross default "
                f"exposure: market_value={gross_jtd}, "
                f"cap_amount={record.fair_value_cap_amount}"
            ),
        )
    return (
        BranchType.NORMAL,
        (
            "batch fair-value cap evidence was eligible but not binding: "
            f"market_value={gross_jtd}, cap_amount={record.fair_value_cap_amount}"
        ),
    )


def _market_value_gross_jtd_array(batch: DrcPositionBatch) -> np.ndarray:
    return np.abs(batch.market_values).astype(np.float64)


def _sorted_indices(batch: DrcPositionBatch) -> tuple[int, ...]:
    return tuple(
        sorted(
            range(batch.row_count),
            key=lambda index: (
                cast(str, batch.position_ids[index]),
                cast(str, batch.source_row_ids[index]),
            ),
        )
    )


__all__ = [
    "batch_fair_value_cap_citations",
    "fair_value_cap_branch_metadata_for_batch",
]
