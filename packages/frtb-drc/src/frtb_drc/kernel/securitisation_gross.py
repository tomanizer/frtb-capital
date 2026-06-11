"""Gross-JTD branch helpers for securitisation non-CTP DRC."""

from __future__ import annotations

from frtb_drc._citations import merge_citations
from frtb_drc._identifiers import slug_path
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    DrcCalculationContext,
    DrcFairValueCapEvidence,
    DrcPosition,
)
from frtb_drc.regimes import get_rule_profile
from frtb_drc.validation import DrcInputError


def fair_value_capped_gross_jtd(
    position: DrcPosition,
    *,
    market_value: float,
    context: DrcCalculationContext | None,
    profile_id: str,
    gross_citations: tuple[str, ...],
    fair_value_cap_citations: tuple[str, ...],
) -> tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]:
    """Return market-value gross JTD after optional fair-value cap evidence.

    Parameters
    ----------
    position : DrcPosition
        Securitisation non-CTP position being grossed.
    market_value : float
        Positive market-value amount before fair-value cap treatment.
    context : DrcCalculationContext | None
        Optional run context containing fair-value cap evidence.
    profile_id : str
        Active DRC rule profile identifier.
    gross_citations : tuple[str, ...]
        Paragraph citations for the market-value gross JTD branch.
    fair_value_cap_citations : tuple[str, ...]
        Paragraph citations for the fair-value cap branch.

    Returns
    -------
    tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]
        Gross JTD amount, selected branch metadata, and citations added by the cap branch.
    """

    evidence = (
        None
        if context is None
        else context.securitisation_non_ctp_fair_value_cap_evidence.get(position.position_id)
    )
    if evidence is None:
        return _no_cap_result(position, market_value, gross_citations)
    if not get_rule_profile(profile_id).securitisation_non_ctp_fair_value_cap_allowed:
        raise DrcInputError(
            f"securitisation non-CTP fair-value cap is not supported for profile {profile_id}"
        )
    citations = merge_citations((*fair_value_cap_citations, *evidence.citation_ids))
    if not evidence.eligible:
        return _ineligible_cap_result(position, market_value, evidence, citations)
    if evidence.fair_value_cap_amount is None:  # pragma: no cover - context validation enforces.
        raise DrcInputError(
            f"fair_value_cap_evidence[{position.position_id}].fair_value_cap_amount is required"
        )
    capped = min(market_value, evidence.fair_value_cap_amount)
    if capped < market_value:
        return _applied_cap_result(position, capped, market_value, evidence, citations)
    return _not_binding_cap_result(position, market_value, evidence, citations)


def _no_cap_result(
    position: DrcPosition,
    market_value: float,
    gross_citations: tuple[str, ...],
) -> tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]:
    return _gross_branch_result(
        market_value,
        branch_id=f"gross-sec-non-ctp-no-fair-value-cap-{slug_path(position.position_id)}",
        branch_type=BranchType.NORMAL,
        source_id=position.position_id,
        reason=(
            "securitisation non-CTP gross default exposure used market value; "
            "no fair-value cap evidence was supplied"
        ),
        citations=gross_citations,
        added_citations=(),
    )


def _ineligible_cap_result(
    position: DrcPosition,
    market_value: float,
    evidence: DrcFairValueCapEvidence,
    citations: tuple[str, ...],
) -> tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]:
    return _gross_branch_result(
        market_value,
        branch_id=f"gross-sec-non-ctp-fair-value-cap-ineligible-{slug_path(position.position_id)}",
        branch_type=BranchType.NORMAL,
        source_id=evidence.source_id,
        reason=(
            "fair-value cap evidence marked the position ineligible; "
            f"reason: {evidence.eligibility_reason}"
        ),
        citations=citations,
        added_citations=citations,
    )


def _applied_cap_result(
    position: DrcPosition,
    capped: float,
    market_value: float,
    evidence: DrcFairValueCapEvidence,
    citations: tuple[str, ...],
) -> tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]:
    return _gross_branch_result(
        capped,
        branch_id=f"gross-sec-non-ctp-fair-value-cap-applied-{slug_path(position.position_id)}",
        branch_type=BranchType.CAP,
        source_id=evidence.source_id,
        reason=(
            "fair-value cap applied to securitisation non-CTP gross "
            f"default exposure: market_value={market_value}, "
            f"cap_amount={evidence.fair_value_cap_amount}"
        ),
        citations=citations,
        added_citations=citations,
    )


def _not_binding_cap_result(
    position: DrcPosition,
    market_value: float,
    evidence: DrcFairValueCapEvidence,
    citations: tuple[str, ...],
) -> tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]:
    return _gross_branch_result(
        market_value,
        branch_id=f"gross-sec-non-ctp-fair-value-cap-not-binding-{slug_path(position.position_id)}",
        branch_type=BranchType.NORMAL,
        source_id=evidence.source_id,
        reason=(
            "fair-value cap evidence was eligible but not binding: "
            f"market_value={market_value}, cap_amount={evidence.fair_value_cap_amount}"
        ),
        citations=citations,
        added_citations=citations,
    )


def _gross_branch_result(
    gross_jtd: float,
    *,
    branch_id: str,
    branch_type: BranchType,
    source_id: str,
    reason: str,
    citations: tuple[str, ...],
    added_citations: tuple[str, ...],
) -> tuple[float, tuple[BranchMetadata, ...], tuple[str, ...]]:
    return (
        gross_jtd,
        (
            BranchMetadata(
                branch_id=branch_id,
                branch_type=branch_type,
                source_id=source_id,
                selected=True,
                reason=reason,
                citations=citations,
            ),
        ),
        added_citations,
    )


__all__ = ["fair_value_capped_gross_jtd"]
