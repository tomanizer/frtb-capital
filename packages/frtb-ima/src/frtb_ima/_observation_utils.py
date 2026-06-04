"""Package-local observation validation helpers for IMA diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis


@dataclass(frozen=True)
class ObservationDateWindow:
    """Most recent observation dates plus optional business-calendar metadata."""

    observation_dates: tuple[date, ...] | None
    calendar_source: str = ""
    calendar_version: str = ""
    calendar_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()


def validate_observation_dates(
    observation_dates: Sequence[date] | None,
    expected_length: int,
    *,
    length_label: str,
) -> tuple[date, ...] | None:
    """Validate optional observation dates for aligned PLA/backtesting vectors."""

    if observation_dates is None:
        return None
    dates = tuple(observation_dates)
    if len(dates) != expected_length:
        raise ValueError(f"observation_dates length must match {length_label}")
    if not all(type(item) is date for item in dates):
        raise TypeError("observation_dates must contain datetime.date values")
    return dates


def select_recent_observation_window(
    observation_dates: tuple[date, ...] | None,
    window_size: int,
    *,
    calendar: BusinessCalendar | None = None,
    validation_label: str,
) -> ObservationDateWindow:
    """Return the most recent observation dates and shared calendar validation metadata."""

    selected_dates = observation_dates[-window_size:] if observation_dates is not None else None
    if calendar is None:
        return ObservationDateWindow(observation_dates=selected_dates)
    if observation_dates is None:
        raise ValueError("observation_dates are required when calendar is supplied")

    calendar_window = calendar.most_recent_business_days(
        window_size,
        as_of_date=observation_dates[-1],
    )
    if selected_dates != calendar_window.business_dates:
        raise ValueError(
            f"{validation_label} window dates must match the supplied business calendar"
        )

    return ObservationDateWindow(
        observation_dates=selected_dates,
        calendar_source=calendar_window.calendar_source,
        calendar_version=calendar_window.calendar_version,
        calendar_basis=calendar_window.basis.value,
        official_holiday_count=calendar_window.official_holiday_count,
        missing_business_dates=calendar_window.missing_business_dates,
    )
