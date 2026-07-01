"""Non-securitisation DRC row-path calculation kernel."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from frtb_drc.capital import CapitalInput, calculate_category_drc
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    CategoryDrc,
    CreditQuality,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    GrossJtd,
    MaturityScaledJtd,
    NetJtd,
)
from frtb_drc.gross_jtd import calculate_gross_jtds
from frtb_drc.maturity import scale_gross_jtds
from frtb_drc.netting import NettingInput, calculate_net_jtds
from frtb_drc.regimes import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    ensure_risk_class_supported,
    get_rule_profile,
)
from frtb_drc.validation import DrcInputError

_US_NPR_ZERO_CATEGORY_CITATION = "US_NPR_210_B_3_III"
_BASEL_ZERO_CATEGORY_CITATION = "BASEL_MAR22_26"
_EU_CRR3_ZERO_CATEGORY_CITATION = "EU_CRR3_ARTICLE_325Y_3_5"
_PRA_ZERO_CATEGORY_CITATION = "PRA_DRC_ARTICLE_325Y"
_US_NPR_NONSEC_NETTING_CITATION = "US_NPR_210_B_2"
_BASEL_NONSEC_NETTING_CITATION = "BASEL_MAR22_19"
_EU_CRR3_NONSEC_NETTING_CITATION = "EU_CRR3_ARTICLE_325X"
_PRA_NONSEC_NETTING_CITATION = "PRA_DRC_ARTICLE_325X"


@dataclass(frozen=True)
class NonSecuritisationCalculation:
    """Non-securitisation records for integration into the public DRC result."""

    gross_jtds: tuple[GrossJtd, ...]
    maturity_scaled_jtds: tuple[MaturityScaledJtd, ...]
    net_jtds: tuple[NetJtd, ...]
    category: CategoryDrc


def calculate_nonsec_drc(
    positions: Iterable[DrcPosition],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> NonSecuritisationCalculation:
    """Calculate the supported non-securitisation DRC path for validated rows.

    Parameters
    ----------
    positions : Iterable[DrcPosition]
        Canonical DRC position records for the non-securitisation path.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    NonSecuritisationCalculation
        Gross, maturity-scaled, net, and category records for result assembly.
    """

    profile = get_rule_profile(profile_id)
    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)
    records = tuple(positions)
    if not records:
        return NonSecuritisationCalculation(
            gross_jtds=(),
            maturity_scaled_jtds=(),
            net_jtds=(),
            category=_zero_nonsec_category(profile_id),
        )
    gross_jtds = calculate_gross_jtds(records, profile_id=profile_id)
    scaled_jtds = scale_gross_jtds(
        (
            (gross_jtd, position.maturity_years)
            for gross_jtd, position in zip(gross_jtds, records, strict=True)
        ),
        profile_id=profile_id,
    )
    gross_by_position = {gross.position_id: gross for gross in gross_jtds}
    scaled_by_position = {scaled.position_id: scaled for scaled in scaled_jtds}
    net_jtds = calculate_net_jtds(
        _netting_inputs(records, gross_by_position, scaled_by_position),
        profile_id=profile_id,
    )
    capital_inputs = _capital_inputs(net_jtds, records)
    category = (
        calculate_category_drc(capital_inputs, profile_id=profile_id)
        if capital_inputs
        else _zero_nonsec_category(profile_id)
    )
    return NonSecuritisationCalculation(
        gross_jtds=gross_jtds,
        maturity_scaled_jtds=scaled_jtds,
        net_jtds=net_jtds,
        category=category,
    )


def nonsec_netting_citation(profile_id: str) -> str:
    """Return the paragraph citation for non-securitisation netting.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    str
        Citation identifier for the applicable non-securitisation netting rule.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_NONSEC_NETTING_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_NONSEC_NETTING_CITATION
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_NONSEC_NETTING_CITATION
    return _US_NPR_NONSEC_NETTING_CITATION


def _netting_inputs(
    positions: tuple[DrcPosition, ...],
    gross_by_position: dict[str, GrossJtd],
    scaled_by_position: dict[str, MaturityScaledJtd],
) -> tuple[NettingInput, ...]:
    inputs: list[NettingInput] = []
    for position in positions:
        if position.seniority is None:  # pragma: no cover - validate_positions enforces this.
            raise DrcInputError("seniority is required for non-securitisation positions")
        inputs.append(
            NettingInput(
                gross_jtd=gross_by_position[position.position_id],
                scaled_jtd=scaled_by_position[position.position_id],
                seniority=DrcSeniority(position.seniority),
            )
        )
    return tuple(inputs)


def _capital_inputs(
    net_jtds: tuple[NetJtd, ...],
    positions: tuple[DrcPosition, ...],
) -> tuple[CapitalInput, ...]:
    positions_by_id = {position.position_id: position for position in positions}
    return tuple(
        CapitalInput(
            net_jtd=net_jtd,
            credit_quality=_credit_quality_for_net_jtd(net_jtd, positions_by_id),
        )
        for net_jtd in net_jtds
    )


def _credit_quality_for_net_jtd(
    net_jtd: NetJtd,
    positions_by_id: dict[str, DrcPosition],
) -> CreditQuality:
    credit_qualities: set[CreditQuality] = set()
    for position_id in net_jtd.position_ids:
        credit_quality = positions_by_id[position_id].credit_quality
        if credit_quality is not None:
            credit_qualities.add(CreditQuality(credit_quality))
    if len(credit_qualities) != 1:
        raise DrcInputError(f"net JTD must map to exactly one credit quality: {net_jtd.net_jtd_id}")
    return next(iter(credit_qualities))


def _zero_nonsec_category(profile_id: str) -> CategoryDrc:
    return CategoryDrc(
        category_id="category-drc-non-securitisation",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(),
        capital=0.0,
        branch_metadata=(
            BranchMetadata(
                branch_id="category-non-securitisation-zero",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.NON_SECURITISATION.value,
                selected=True,
                reason="all supported net JTD records are zero",
                citations=(_zero_nonsec_category_citation(profile_id),),
            ),
        ),
    )


def _zero_nonsec_category_citation(profile_id: str) -> str:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_ZERO_CATEGORY_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_ZERO_CATEGORY_CITATION
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_ZERO_CATEGORY_CITATION
    return _US_NPR_ZERO_CATEGORY_CITATION


__all__ = [
    "NonSecuritisationCalculation",
    "calculate_nonsec_drc",
    "nonsec_netting_citation",
]
