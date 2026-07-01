"""Public DRC result assembly helpers.

This module owns citation, branch metadata, and attribution-support assembly for
the row-oriented public DRC API. Default-risk capital formulas remain in kernel
modules; this layer preserves the public result audit shape.
"""

from __future__ import annotations

from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    CategoryDrc,
    CreditQuality,
    DrcCalculationContext,
    DrcPosition,
    DrcRiskClass,
    GrossJtd,
    MaturityScaledJtd,
    NetJtd,
)
from frtb_drc.kernel.nonsec import nonsec_netting_citation
from frtb_drc.reference_data import get_risk_weight_rule
from frtb_drc.regimes import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    DrcRuleProfile,
)
from frtb_drc.risk_weight_evidence import effective_risk_weights


def _collect_citations(
    *,
    gross_jtds: tuple[GrossJtd, ...],
    scaled_jtds: tuple[MaturityScaledJtd, ...],
    net_jtds: tuple[NetJtd, ...],
    categories: tuple[CategoryDrc, ...],
    profile_id: str,
) -> tuple[str, ...]:
    """Collect deterministic citation ids for the public row-result contract.

    Parameters
    ----------
    gross_jtds : tuple[GrossJtd, ...]
        Gross jump-to-default records retained by the public row API.
    scaled_jtds : tuple[MaturityScaledJtd, ...]
        Maturity-scaled JTD records retained by the public row API.
    net_jtds : tuple[NetJtd, ...]
        Net JTD records produced by the supported path kernels.
    categories : tuple[CategoryDrc, ...]
        Risk-class category capital results.
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Sorted citation identifiers attached to the public capital result.
    """

    citation_ids: set[str] = set()
    if profile_id == US_NPR_2_0_PROFILE_ID:
        citation_ids.add("US_NPR_210_SCOPE")
    if any(
        DrcRiskClass(record.risk_class) == DrcRiskClass.NON_SECURITISATION for record in net_jtds
    ):
        citation_ids.add(nonsec_netting_citation(profile_id))
    if any(
        DrcRiskClass(record.risk_class) == DrcRiskClass.SECURITISATION_NON_CTP
        for record in net_jtds
    ):
        citation_ids.update(_securitisation_non_ctp_public_api_citations(profile_id))
    if (
        any(
            DrcRiskClass(record.risk_class) == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
            for record in net_jtds
        )
    ):
        citation_ids.update(_ctp_public_api_citations(profile_id))
    for gross_jtd in gross_jtds:
        citation_ids.update(gross_jtd.citations)
        citation_ids.update(_branch_citations(gross_jtd.branch_metadata))
    for scaled_jtd in scaled_jtds:
        citation_ids.update(scaled_jtd.citations)
        citation_ids.update(_branch_citations(scaled_jtd.branch_metadata))
    for net_jtd in net_jtds:
        citation_ids.update(_branch_citations(net_jtd.branch_metadata))
        for rejected_offset in net_jtd.rejected_offsets:
            citation_ids.update(rejected_offset.citations)
    for category in categories:
        citation_ids.update(_branch_citations(category.branch_metadata))
        for bucket in category.bucket_results:
            citation_ids.update(bucket.citations)
            citation_ids.update(bucket.hbr.citations)
            citation_ids.update(_branch_citations(bucket.branch_metadata))
            citation_ids.update(_branch_citations(bucket.hbr.branch_metadata))
    return tuple(sorted(citation_ids))


def _risk_weights_by_position(
    positions: tuple[DrcPosition, ...],
    *,
    context: DrcCalculationContext,
    profile: DrcRuleProfile,
) -> dict[str, float]:
    """Return per-position risk weights for public-result attribution support.

    Parameters
    ----------
    positions : tuple[DrcPosition, ...]
        FX-normalized canonical DRC positions.
    context : DrcCalculationContext
        Run context containing securitisation and CTP evidence.
    profile : DrcRuleProfile
        Active DRC rule profile.

    Returns
    -------
    dict[str, float]
        Risk weight keyed by position id where a supported path has evidence.
    """

    weights: dict[str, float] = {}
    sec_weights = effective_risk_weights(
        context,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
    )
    ctp_weights = effective_risk_weights(
        context,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )
    for position in positions:
        risk_class = DrcRiskClass(position.risk_class)
        if risk_class == DrcRiskClass.NON_SECURITISATION:
            if position.credit_quality is None or position.bucket_key is None:
                continue
            weights[position.position_id] = get_risk_weight_rule(
                position.bucket_key,
                CreditQuality(position.credit_quality),
                profile_id=profile.profile_id,
            ).risk_weight
        elif risk_class == DrcRiskClass.SECURITISATION_NON_CTP:
            if position.position_id in sec_weights:
                weights[position.position_id] = sec_weights[position.position_id]
        elif risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
            if position.position_id in ctp_weights:
                weights[position.position_id] = ctp_weights[position.position_id]
    return weights


def _run_branch_metadata(
    categories: tuple[CategoryDrc, ...],
    *,
    profile_id: str,
) -> tuple[BranchMetadata, ...]:
    """Build public API branch metadata for selected DRC risk-class paths.

    Parameters
    ----------
    categories : tuple[CategoryDrc, ...]
        Risk-class category capital results included in the run.
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[BranchMetadata, ...]
        Branch records for the public row API orchestration path.
    """

    branches: list[BranchMetadata] = []
    risk_classes = {DrcRiskClass(category.risk_class) for category in categories}
    if DrcRiskClass.NON_SECURITISATION in risk_classes:
        branches.append(
            BranchMetadata(
                branch_id="drc-non-securitisation-public-api",
                branch_type=BranchType.NORMAL,
                source_id=profile_id,
                selected=True,
                reason=(
                    "public API executed supported non-securitisation path; "
                    "Euler attribution is not calculated"
                ),
                citations=("US_NPR_210_SCOPE", "US_NPR_210_B_3_III"),
            )
        )
    if DrcRiskClass.SECURITISATION_NON_CTP in risk_classes:
        branches.append(
            BranchMetadata(
                branch_id="drc-securitisation-non-ctp-public-api",
                branch_type=BranchType.NORMAL,
                source_id=profile_id,
                selected=True,
                reason=(
                    "public API executed supported securitisation non-CTP path "
                    "using run-scoped banking-book securitisation risk-weight "
                    "evidence; Euler attribution is not calculated"
                ),
                citations=_securitisation_non_ctp_public_api_citations(profile_id),
            )
        )
    if DrcRiskClass.CORRELATION_TRADING_PORTFOLIO in risk_classes:
        branches.append(
            BranchMetadata(
                branch_id="drc-ctp-public-api",
                branch_type=BranchType.NORMAL,
                source_id=profile_id,
                selected=True,
                reason=(
                    "public API executed supported CTP path using run-scoped "
                    "risk weights and offset-group evidence; Euler attribution "
                    "is not calculated"
                ),
                citations=_ctp_public_api_citations(profile_id),
            )
        )
    return tuple(branches)


def _branch_citations(branches: tuple[BranchMetadata, ...]) -> set[str]:
    citation_ids: set[str] = set()
    for branch in branches:
        citation_ids.update(branch.citations)
    return citation_ids


def _securitisation_non_ctp_public_api_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return (
            "BASEL_MAR22_27",
            "BASEL_MAR22_28",
            "BASEL_MAR22_29",
            "BASEL_MAR22_30",
            "BASEL_MAR22_35",
        )
    if profile_id == EU_CRR3_PROFILE_ID:
        return ("EU_CRR3_ARTICLE_325Z", "EU_CRR3_ARTICLE_325AA")
    return ("US_NPR_210_C_1", "US_NPR_210_C_2", "US_NPR_210_C_3_IV")


def _ctp_public_api_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return ("BASEL_MAR22_36", "BASEL_MAR22_39", "BASEL_MAR22_45")
    if profile_id == EU_CRR3_PROFILE_ID:
        return (
            "EU_CRR3_ARTICLE_325AB",
            "EU_CRR3_ARTICLE_325AC",
            "EU_CRR3_ARTICLE_325AD",
        )
    return ("US_NPR_210_D_1", "US_NPR_210_D_2", "US_NPR_210_D_3_V")


__all__ = [
    "_collect_citations",
    "_risk_weights_by_position",
    "_run_branch_metadata",
]
