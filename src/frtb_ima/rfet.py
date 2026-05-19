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

# Quantitative thresholds keyed on whether LH is short (<= 20) or long (> 20)
_THRESHOLD_SHORT_LH = 24   # for LH 10 or 20
_THRESHOLD_LONG_LH  = 16   # for LH 40, 60, or 120

_LOOKBACK_DAYS = 365        # "prior 12 months" approximated as 365 calendar days


def _quantitative_threshold(lh: LiquidityHorizon) -> int:
    return _THRESHOLD_SHORT_LH if lh.value <= 20 else _THRESHOLD_LONG_LH


def count_eligible_observations(
    observations: Sequence[RealPriceObservation],
    risk_factor_name: str,
    as_of_date: date,
) -> int:
    """
    Count unique-date real-price observations for a risk factor in prior 12 months.

    Per prototype assumption: at most one observation counts per calendar date.
    """
    window_start = as_of_date - timedelta(days=_LOOKBACK_DAYS)

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
) -> bool:
    """Return True if the risk factor meets the quantitative real-price threshold."""
    count = count_eligible_observations(observations, risk_factor.name, as_of_date)
    threshold = _quantitative_threshold(risk_factor.liquidity_horizon)
    return count >= threshold


def classify_risk_factor(
    risk_factor: RiskFactor,
    observations: Sequence[RealPriceObservation],
    qualitative_pass: bool,
    as_of_date: date,
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

    quant_pass = passes_quantitative_test(observations, risk_factor, as_of_date)
    if quant_pass:
        return ModellabilityStatus.MODELLABLE
    else:
        return ModellabilityStatus.TYPE_A_NMRF
