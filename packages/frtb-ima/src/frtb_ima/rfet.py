"""
Risk Factor Eligibility Test (RFET) and modellability classification.

RFET mechanics for the NPR 2.0 / Basel FRTB IMA profile:

Quantitative thresholds:
    - LH <= 20 days: >= 24 real-price observations in the prior 12 months.
    - LH >  20 days: >= 16 real-price observations in the prior 12 months.

At most one eligible observation is counted per calendar date.

Qualitative test: passed in as a boolean (external governance decision).

Classification logic:
    - qualitative AND quantitative pass  -> MODELLABLE
    - qualitative pass, quantitative fail -> TYPE_A_NMRF
    - qualitative fail                    -> TYPE_B_NMRF

Known unsupported evidence controls:
    - Time-zone normalisation for cross-market risk factors.
    - New-issuance pro-rating stub.

Regulatory traceability:
    Basel MAR31.12-MAR31.18 RFET; U.S. NPR 2.0 proposed Sec. __.212 Type A /
    Type B NMRF taxonomy; EU CRR Article 325be and Delegated Regulation (EU)
    2022/2060. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from datetime import date, timedelta

from frtb_ima.calendar import BusinessCalendar
from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskFactor,
)
from frtb_ima.regimes import RegulatoryPolicy

# Quantitative thresholds keyed on whether LH is short (<= 20) or long (> 20).
_THRESHOLD_SHORT_LH = 24  # for LH 10 or 20
_THRESHOLD_LONG_LH = 16  # for LH 40, 60, or 120
_SHORT_LH_MAX_DAYS = 20

_LOOKBACK_DAYS = 365  # Non-compliant compatibility proxy; MAR31.12 requires 12 months.
_LOOKBACK_PROXY_WARNING = (
    "lookback_days path is a 365-day approximation, not an exact 12-month window "
    "(Basel MAR31.12). Supply a BusinessCalendar for regulatory compliance."
)


def _lineage_key(observation: RealPriceObservation) -> tuple[object, ...]:
    return (
        observation.observation_date,
        observation.source,
        observation.vendor_id,
        observation.venue,
        observation.feed,
        observation.data_pool_id,
    )


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
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> int:
    """Count eligible unique-date observations for a risk factor.

    Basel MAR31.12 counts real-price observations over the prior 12 months.
    Basel MAR31.13-MAR31.14 require real prices to be verifiable and prevent
    multiple counts from the same source/vendor lineage. This helper excludes
    ``verifiable=False`` observations, deduplicates identical lineage keys, and
    then applies the one-count-per-calendar-date rule.

    When ``calendar`` is omitted, ``lookback_days`` remains a compatibility
    proxy and is not an exact MAR31.12 prior-12-month window.

    Parameters
    ----------
    observations : Sequence[RealPriceObservation]
        Real-price observations to filter.
    risk_factor_name : str
        Risk factor to count.
    as_of_date : date
        Inclusive window end date.
    lookback_days : int, optional
        Compatibility lookback-day proxy used only when ``calendar`` is omitted.
    calendar : BusinessCalendar | None, optional
        Caller-supplied calendar for the exact prior-12-month business window.
    shifted_start_date : date | None, optional
        Optional policy-approved shifted window start.
    shifted_end_date : date | None, optional
        Optional policy-approved shifted window end.
    shift_reason : str, optional
        Policy rationale for a shifted calendar window.

    Returns
    -------
    int
        Number of unique calendar dates with at least one eligible real-price
        observation within the lookback window.
    """
    if calendar is None:
        if lookback_days <= 0:
            raise ValueError(f"lookback_days must be positive, got {lookback_days}")
        warnings.warn(_LOOKBACK_PROXY_WARNING, DeprecationWarning, stacklevel=2)
        window_start = as_of_date - timedelta(days=lookback_days)
        window_end = as_of_date
        business_dates: set[date] | None = None
    else:
        window = calendar.exact_twelve_month_window(
            as_of_date,
            shifted_start_date=shifted_start_date,
            shifted_end_date=shifted_end_date,
            shift_reason=shift_reason,
        )
        window_start = window.start_date
        window_end = window.end_date
        business_dates = set(window.business_dates)

    eligible_dates: set[date] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    for obs in observations:
        if obs.risk_factor_name != risk_factor_name:
            continue
        if not (window_start <= obs.observation_date <= window_end):
            continue
        if business_dates is not None and obs.observation_date not in business_dates:
            continue
        if not obs.verifiable:
            continue
        lineage_key = _lineage_key(obs)
        if lineage_key in seen_lineage_keys:
            continue
        if obs.observation_date in eligible_dates:
            continue
        seen_lineage_keys.add(lineage_key)
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
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> bool:
    """Return True if the risk factor meets the quantitative real-price threshold.

    Parameters
    ----------
    observations : Sequence[RealPriceObservation]
        Real-price observations to filter.
    risk_factor : RiskFactor
        Risk factor.
    as_of_date : date
        As of date.
    short_lh_threshold : int, optional
        Short lh threshold.
    long_lh_threshold : int, optional
        Long lh threshold.
    short_lh_max_days : int, optional
        Short lh max days.
    lookback_days : int, optional
        Compatibility lookback-day proxy used only when ``calendar`` is omitted.
    calendar : BusinessCalendar | None, optional
        Caller-supplied calendar for the exact prior-12-month business window.
    shifted_start_date : date | None, optional
        Shifted start date.
    shifted_end_date : date | None, optional
        Shifted end date.
    shift_reason : str, optional
        Shift reason.

    Returns
    -------
    bool
        ``True`` if the eligible observation count meets or exceeds the
        regulatory threshold for the risk factor's liquidity horizon.
    """
    count = count_eligible_observations(
        observations,
        risk_factor.name,
        as_of_date,
        lookback_days=lookback_days,
        calendar=calendar,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
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
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> ModellabilityStatus:
    """Classify a risk factor as MODELLABLE, TYPE_A_NMRF, or TYPE_B_NMRF.

    Parameters
    ----------
    risk_factor : RiskFactor
        Risk factor to classify.
    observations : Sequence[RealPriceObservation]
        All available real-price observations.
    qualitative_pass : bool
        Externally determined qualitative governance result.
    as_of_date : date
        As of date.
    short_lh_threshold : int, optional
        Short lh threshold.
    long_lh_threshold : int, optional
        Long lh threshold.
    short_lh_max_days : int, optional
        Short lh max days.
    lookback_days : int, optional
        Compatibility lookback-day proxy used only when ``calendar`` is omitted.
    calendar : BusinessCalendar | None, optional
        Caller-supplied calendar for the exact prior-12-month business window.
    shifted_start_date : date | None, optional
        Shifted start date.
    shifted_end_date : date | None, optional
        Shifted end date.
    shift_reason : str, optional
        Shift reason.

    Returns
    -------
    ModellabilityStatus
        Modellability classification: ``MODELLABLE``, ``TYPE_A_NMRF``, or
        ``TYPE_B_NMRF``.
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
        calendar=calendar,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
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
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> ModellabilityStatus:
    """Classify a risk factor using policy RFET parameters.

    This wrapper is intentionally limited to policies that support the U.S.
    Type A / Type B NMRF taxonomy. EU and UK profiles currently raise an
    explicit unsupported-feature error rather than returning misleading labels.
    A ``BusinessCalendar`` is required for regulatory compliance because
    Basel MAR31.12 and NPR 2.0 Sec. __.212 require an exact prior-12-month
    observation window.

    Parameters
    ----------
    risk_factor : RiskFactor
        Risk factor.
    observations : Sequence[RealPriceObservation]
        Observations.
    qualitative_pass : bool
        Qualitative pass.
    as_of_date : date
        As of date.
    policy : RegulatoryPolicy
        Policy.
    calendar : BusinessCalendar | None, optional
        Required caller-supplied calendar for the exact prior-12-month window.
    shifted_start_date : date | None, optional
        Shifted start date.
    shifted_end_date : date | None, optional
        Shifted end date.
    shift_reason : str, optional
        Shift reason.

    Returns
    -------
    ModellabilityStatus
        Modellability classification under the supplied regulatory policy.
    """
    policy.require_type_a_type_b_taxonomy()
    if calendar is None:
        raise ValueError(
            "calendar is required for classify_risk_factor_for_policy; "
            "Basel MAR31.12 and NPR 2.0 Sec. __.212 require an exact prior "
            "12-month RFET observation window"
        )
    return classify_risk_factor(
        risk_factor,
        observations,
        qualitative_pass=qualitative_pass,
        as_of_date=as_of_date,
        short_lh_threshold=policy.rfet_short_lh_threshold,
        long_lh_threshold=policy.rfet_long_lh_threshold,
        short_lh_max_days=policy.rfet_short_lh_max_days,
        lookback_days=policy.rfet_lookback_days,
        calendar=calendar,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
    )
