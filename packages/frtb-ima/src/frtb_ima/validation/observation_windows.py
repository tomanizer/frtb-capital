"""Observation-window validation helpers for IMA diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis

__all__ = [
    "ObservationDateWindow",
    "require_positive_observation_count",
    "require_positive_optional_observation_count",
    "require_window_minimum_pair",
    "select_recent_observation_window",
    "validate_observation_dates",
]


@dataclass(frozen=True)
class ObservationDateWindow:
    """Most recent observation dates plus optional business-calendar metadata."""

    observation_dates: tuple[date, ...] | None
    calendar_source: str = ""
    calendar_version: str = ""
    calendar_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()


def require_positive_observation_count(
    value: int,
    *,
    field: str,
    include_value: bool = True,
) -> None:
    """Require a positive observation count for a named window field.

    Parameters
    ----------
    value : int
        Observation count value to validate.
    field : str
        Field name to include in validation errors.
    include_value : bool, optional
        Include the invalid value in the error message when true.
    """

    if value <= 0:
        message = f"{field} must be positive"
        if include_value:
            message = f"{message}, got {value}"
        raise ValueError(message)


def require_positive_optional_observation_count(
    value: int | None,
    *,
    field: str,
) -> None:
    """Require a positive observation count when an optional field is supplied.

    Parameters
    ----------
    value : int | None
        Optional observation count to validate.
    field : str
        Field name to include in validation errors.
    """

    if value is not None and value <= 0:
        raise ValueError(f"{field} must be positive when provided, got {value}")


def require_window_minimum_pair(
    *,
    window_value: int,
    minimum_value: int,
    window_field: str,
    minimum_field: str,
) -> None:
    """Require a minimum observation count to cover a selected window.

    Parameters
    ----------
    window_value : int
        Window observation count.
    minimum_value : int
        Minimum required observation count.
    window_field : str
        Window field name to include in validation errors.
    minimum_field : str
        Minimum field name to include in validation errors.
    """

    if minimum_value < window_value:
        raise ValueError(f"{minimum_field} cannot be less than {window_field}")


def validate_observation_dates(
    observation_dates: Sequence[date] | None,
    expected_length: int,
    *,
    length_label: str,
) -> tuple[date, ...] | None:
    """Validate optional observation dates for aligned PLA/backtesting vectors.

    Dates must be in non-decreasing order so positional window selection
    corresponds to the chronologically most recent observations.

    Parameters
    ----------
    observation_dates : Sequence[date] | None
        Observation dates.
    expected_length : int
        Expected length.
    length_label : str
        Length label.

    Returns
    -------
    tuple[date, ...] | None
        Validated observation dates, or ``None`` when dates were not supplied.
    """

    if observation_dates is None:
        return None
    dates = tuple(observation_dates)
    if len(dates) != expected_length:
        raise ValueError(f"observation_dates length must match {length_label}")
    if not all(type(item) is date for item in dates):
        raise TypeError("observation_dates must contain datetime.date values")
    for index in range(1, len(dates)):
        if dates[index] < dates[index - 1]:
            raise ValueError(
                "observation_dates must be in non-decreasing order; "
                f"date at index {index} ({dates[index]}) precedes "
                f"index {index - 1} ({dates[index - 1]})"
            )
    return dates


def select_recent_observation_window(
    observation_dates: tuple[date, ...] | None,
    window_size: int,
    *,
    calendar: BusinessCalendar | None = None,
    validation_label: str,
) -> ObservationDateWindow:
    """Return the most recent observation dates and shared calendar validation metadata.
    Parameters
    ----------
    observation_dates : tuple[date, ...] | None
        Observation dates.
    window_size : int
        Window size.
    calendar : BusinessCalendar | None, optional
        Calendar.
    validation_label : str
        Validation label.

    Returns
    -------
    ObservationDateWindow
        Result of the operation.
    """

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
