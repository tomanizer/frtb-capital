"""
Risk Factor Eligibility Test (RFET) and modellability classification.

Working assumptions (NPR 2.0 / Basel FRTB IMA prototype):

Quantitative thresholds:
    - LH <= 20 days: >= 24 real-price observations in the prior 12 months.
    - LH >  20 days: >= 16 real-price observations in the prior 12 months.

At most one eligible observation is counted per calendar date.

Qualitative test: passed in as a boolean (external governance decision).

Classification logic:
    - qualitative AND quantitative pass  -> MODELLABLE
    - qualitative pass, quantitative fail -> TYPE_A_NMRF
    - qualitative fail                    -> TYPE_B_NMRF

TODOs (not implemented in prototype):
    - Vendor/source deduplication across observation feeds.
    - Time-zone normalisation for cross-market risk factors.
    - New-issuance pro-rating stub.

Regulatory traceability:
    Basel MAR31 RFET; U.S. NPR 2.0 Type A / Type B NMRF working assumptions;
    EU CRR Article 325be and Delegated Regulation (EU) 2022/2060. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskFactor,
)
from frtb_ima.regimes import RegulatoryPolicy

# Quantitative thresholds keyed on whether LH is short (<= 20) or long (> 20)
_THRESHOLD_SHORT_LH = 24   # for LH 10 or 20
_THRESHOLD_LONG_LH  = 16   # for LH 40, 60, or 120
_SHORT_LH_MAX_DAYS = 20

_LOOKBACK_DAYS = 365        # "prior 12 months" approximated as 365 calendar days


def _quantitative_threshold(
    lh: LiquidityHorizon,
    short_lh_threshold: int = _THRESHOLD_SHORT_LH,
    long_lh_threshold: int = _THRESHOLD_LONG_LH,
    short_lh_max_days: int = _SHORT_LH_MAX_DAYS,
) -> int:
    return short_lh_threshold if lh.value <= short_lh_max_days else long_lh_threshold


def count_eligible_observations(
    observations: Sequence[RealPriceObservation],
    risk_factor_name: str,
    as_of_date: date,
    lookback_days: int = _LOOKBACK_DAYS,
) -> int:
    """
    Count unique-date real-price observations for a risk factor in prior 12 months.

    Per prototype assumption: at most one observation counts per calendar date.
    """
    if lookback_days <= 0:
        raise ValueError(f"lookback_days must be positive, got {lookback_days}")

    window_start = as_of_date - timedelta(days=lookback_days)

    eligible_dates: set[date] = set()
    for obs in observations:
        if obs.risk_factor_name != risk_factor_name:
            continue
        if window_start <= obs.observation_date <= as_of_date:
            eligible_dates.add(obs.observation_date)

    return len(eligible_dates)


def passes_quantitative_test(
    observations: Sequence[RealPriceObservation],
    risk_factor: RiskFactor,
    as_of_date: date,
    short_lh_threshold: int = _THRESHOLD_SHORT_LH,
    long_lh_threshold: int = _THRESHOLD_LONG_LH,
    short_lh_max_days: int = _SHORT_LH_MAX_DAYS,
    lookback_days: int = _LOOKBACK_DAYS,
) -> bool:
    """Return True if the risk factor meets the quantitative real-price threshold."""
    count = count_eligible_observations(
        observations,
        risk_factor.name,
        as_of_date,
        lookback_days=lookback_days,
    )
    threshold = _quantitative_threshold(
        risk_factor.liquidity_horizon,
        short_lh_threshold=short_lh_threshold,
        long_lh_threshold=long_lh_threshold,
        short_lh_max_days=short_lh_max_days,
    )
    return count >= threshold


def classify_risk_factor(
    risk_factor: RiskFactor,
    observations: Sequence[RealPriceObservation],
    qualitative_pass: bool,
    as_of_date: date,
    short_lh_threshold: int = _THRESHOLD_SHORT_LH,
    long_lh_threshold: int = _THRESHOLD_LONG_LH,
    short_lh_max_days: int = _SHORT_LH_MAX_DAYS,
    lookback_days: int = _LOOKBACK_DAYS,
) -> ModellabilityStatus:
    """
    Classify a risk factor as MODELLABLE, TYPE_A_NMRF, or TYPE_B_NMRF.

    Args:
        risk_factor:     The risk factor to classify.
        observations:    All available real-price observations (any factor).
        qualitative_pass: Whether this factor passes the qualitative test
                         (governance / expert judgement — external input).
        as_of_date:      Classification reference date.

    Returns:
        ModellabilityStatus enum value.
    """
    if not qualitative_pass:
        return ModellabilityStatus.TYPE_B_NMRF

    quant_pass = passes_quantitative_test(
        observations,
        risk_factor,
        as_of_date,
        short_lh_threshold=short_lh_threshold,
        long_lh_threshold=long_lh_threshold,
        short_lh_max_days=short_lh_max_days,
        lookback_days=lookback_days,
    )
    if quant_pass:
        return ModellabilityStatus.MODELLABLE
    else:
        return ModellabilityStatus.TYPE_A_NMRF


def classify_risk_factor_for_policy(
    risk_factor: RiskFactor,
    observations: Sequence[RealPriceObservation],
    qualitative_pass: bool,
    as_of_date: date,
    policy: RegulatoryPolicy,
) -> ModellabilityStatus:
    """
    Classify a risk factor using policy RFET parameters.

    This wrapper is intentionally limited to policies that support the U.S.
    Type A / Type B NMRF taxonomy. EU and UK profiles currently raise an
    explicit unsupported-feature error rather than returning misleading labels.
    """
    policy.require_supported("type_a_type_b_nmrf_taxonomy")
    return classify_risk_factor(
        risk_factor,
        observations,
        qualitative_pass=qualitative_pass,
        as_of_date=as_of_date,
        short_lh_threshold=policy.rfet_short_lh_threshold,
        long_lh_threshold=policy.rfet_long_lh_threshold,
        short_lh_max_days=policy.rfet_short_lh_max_days,
        lookback_days=policy.rfet_lookback_days,
    )
