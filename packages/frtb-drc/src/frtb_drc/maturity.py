"""Maturity weighting for DRC gross JTD records."""

from __future__ import annotations

import math
from collections.abc import Iterable

from frtb_drc.data_models import BranchMetadata, BranchType, GrossJtd, MaturityScaledJtd
from frtb_drc.reference_data import get_maturity_policy
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID
from frtb_drc.validation import DrcInputError


def calculate_maturity_weight(
    maturity_years: float,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[float, bool, str]:
    """Return maturity weight, floor flag, and citation id."""

    if not math.isfinite(maturity_years):
        raise DrcInputError("maturity_years must be finite")
    if maturity_years < 0:
        raise DrcInputError("maturity_years must be non-negative")

    policy = get_maturity_policy(profile_id)
    if maturity_years >= policy.full_weight_years:
        return 1.0, False, policy.citation_id
    floor_applied = maturity_years < policy.floor_years
    effective_maturity = max(maturity_years, policy.floor_years)
    return effective_maturity / policy.full_weight_years, floor_applied, policy.citation_id


def scale_gross_jtd(
    gross_jtd: GrossJtd,
    maturity_years: float,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> MaturityScaledJtd:
    """Apply maturity weighting to a gross JTD record."""

    weight, floor_applied, citation_id = calculate_maturity_weight(
        maturity_years,
        profile_id=profile_id,
    )
    branch_metadata = ()
    if floor_applied:
        branch_metadata = (
            BranchMetadata(
                branch_id=f"branch-maturity-floor-{gross_jtd.gross_jtd_id}",
                branch_type=BranchType.FLOOR,
                source_id=gross_jtd.gross_jtd_id,
                selected=True,
                reason="maturity below profile floor",
                citations=(citation_id,),
            ),
        )

    return MaturityScaledJtd(
        scaled_jtd_id=f"scaled-{gross_jtd.position_id}",
        gross_jtd_id=gross_jtd.gross_jtd_id,
        position_id=gross_jtd.position_id,
        gross_jtd=gross_jtd.gross_jtd,
        maturity_years=maturity_years,
        maturity_weight=weight,
        scaled_jtd=gross_jtd.gross_jtd * weight,
        floor_applied=floor_applied,
        citations=(citation_id,),
        branch_metadata=branch_metadata,
    )


def scale_gross_jtds(
    gross_jtds_with_maturity: Iterable[tuple[GrossJtd, float]],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[MaturityScaledJtd, ...]:
    """Scale gross JTD records in input order."""

    return tuple(
        scale_gross_jtd(gross_jtd, maturity_years, profile_id=profile_id)
        for gross_jtd, maturity_years in gross_jtds_with_maturity
    )
