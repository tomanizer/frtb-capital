"""RFET observation-window validation stage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.regimes import RegulatoryPolicy


@dataclass(frozen=True)
class _RFETObservationWindow:
    lookback_start: date
    lookback_end: date
    lookback_basis: str
    calendar_source: str
    calendar_version: str
    official_holiday_count: int
    missing_business_dates: tuple[date, ...]
    business_dates: frozenset[date] | None
    official_holidays: frozenset[date]


def _rfet_observation_window(
    as_of_date: date,
    policy: RegulatoryPolicy,
    *,
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> _RFETObservationWindow:
    if calendar is None:
        return _RFETObservationWindow(
            lookback_start=as_of_date - timedelta(days=policy.rfet_lookback_days),
            lookback_end=as_of_date,
            lookback_basis=ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value,
            calendar_source="",
            calendar_version="",
            official_holiday_count=0,
            missing_business_dates=(),
            business_dates=None,
            official_holidays=frozenset(),
        )

    window = calendar.exact_twelve_month_window(
        as_of_date,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
    )
    return _RFETObservationWindow(
        lookback_start=window.start_date,
        lookback_end=window.end_date,
        lookback_basis=window.basis.value,
        calendar_source=window.calendar_source,
        calendar_version=window.calendar_version,
        official_holiday_count=window.official_holiday_count,
        missing_business_dates=window.missing_business_dates,
        business_dates=frozenset(window.business_dates),
        official_holidays=frozenset(window.official_holidays),
    )
