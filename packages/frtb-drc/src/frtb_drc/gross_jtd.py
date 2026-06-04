"""Gross jump-to-default calculations for DRC."""

from __future__ import annotations

from collections.abc import Iterable

from frtb_drc.data_models import (
    DefaultDirection,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    GrossJtd,
)
from frtb_drc.reference_data import get_lgd_rule
from frtb_drc.regimes import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    ensure_risk_class_supported,
    get_rule_profile,
)
from frtb_drc.validation import DrcInputError, validate_position, validate_positions

_US_NPR_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_BASEL_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_EU_CRR3_FORMULA_CITATIONS = ("EU_CRR3_ARTICLE_325W",)


def calculate_gross_jtd(
    position: DrcPosition,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> GrossJtd:
    """Calculate cited gross JTD for one supported non-securitisation position.
    Parameters
    ----------
    position : DrcPosition
        Position.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    GrossJtd
        Result of the operation.
    """

    validate_position(position, profile_id=profile_id)
    profile = get_rule_profile(profile_id)
    risk_class = DrcRiskClass(position.risk_class)
    ensure_risk_class_supported(profile, risk_class)
    if risk_class != DrcRiskClass.NON_SECURITISATION:
        raise DrcInputError(f"gross JTD is not implemented for {risk_class.value}")
    if position.seniority is None:
        raise DrcInputError("seniority is required for gross JTD")
    seniority = DrcSeniority(position.seniority)
    default_direction = DefaultDirection(position.default_direction)
    if position.lgd_override is not None:
        raise DrcInputError("explicit LGD overrides are not supported by the selected profile")

    lgd_rule = get_lgd_rule(
        seniority,
        profile_id=profile.profile_id,
        is_defaulted=position.is_defaulted,
    )
    pnl_component = _resolve_pnl_component(position)
    signed_notional = _signed_notional(position)
    raw_jtd = lgd_rule.lgd_rate * signed_notional + pnl_component
    if default_direction == DefaultDirection.LONG:
        gross_jtd = max(raw_jtd, 0.0)
    else:
        gross_jtd = abs(min(raw_jtd, 0.0))

    return GrossJtd(
        gross_jtd_id=f"gross-{position.position_id}",
        position_id=position.position_id,
        risk_class=risk_class,
        issuer_or_tranche_key=_issuer_or_tranche_key(position),
        bucket_key=position.bucket_key or "",
        default_direction=default_direction,
        lgd_rate=lgd_rule.lgd_rate,
        lgd_source=lgd_rule.description,
        notional=abs(position.notional),
        pnl_component=pnl_component,
        gross_jtd=gross_jtd,
        citations=(
            *_gross_jtd_formula_citations(profile.profile_id),
            lgd_rule.citation_id,
            *position.citation_ids,
        ),
    )


def calculate_gross_jtds(
    positions: Iterable[DrcPosition],
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> tuple[GrossJtd, ...]:
    """Calculate gross JTD records in input order.
    Parameters
    ----------
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    profile_id : str, optional
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[GrossJtd, ...]
        Result of the operation.
    """

    validated_positions = validate_positions(positions, profile_id=profile_id)
    return tuple(
        calculate_gross_jtd(position, profile_id=profile_id) for position in validated_positions
    )


def _signed_notional(position: DrcPosition) -> float:
    notional_magnitude = abs(position.notional)
    if DefaultDirection(position.default_direction) == DefaultDirection.LONG:
        return notional_magnitude
    return -notional_magnitude


def _resolve_pnl_component(position: DrcPosition) -> float:
    if position.cumulative_pnl is not None:
        return position.cumulative_pnl
    if position.market_value is None:
        raise DrcInputError("cumulative_pnl or market_value is required for gross JTD")
    if DefaultDirection(position.default_direction) == DefaultDirection.LONG:
        return position.market_value - abs(position.notional)
    return abs(position.notional) - position.market_value


def _issuer_or_tranche_key(position: DrcPosition) -> str:
    if position.issuer_id is not None:
        return position.issuer_id
    if position.tranche_id is not None:
        return position.tranche_id
    raise DrcInputError("issuer_id or tranche_id is required for gross JTD")


def _gross_jtd_formula_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_FORMULA_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_FORMULA_CITATIONS
    return _US_NPR_FORMULA_CITATIONS
