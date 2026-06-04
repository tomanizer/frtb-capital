from __future__ import annotations

from datetime import date, datetime

import pytest

from frtb_ima._observation_utils import (
    select_recent_observation_window,
    validate_observation_dates,
)
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis


def test_validate_observation_dates_accepts_none() -> None:
    assert validate_observation_dates(None, 2, length_label="APL/HPL") is None


def test_validate_observation_dates_returns_tuple() -> None:
    dates = [date(2026, 1, 1), date(2026, 1, 2)]

    assert validate_observation_dates(dates, 2, length_label="APL/HPL") == tuple(dates)


def test_validate_observation_dates_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="observation_dates length must match APL/HPL"):
        validate_observation_dates([date(2026, 1, 1)], 2, length_label="APL/HPL")


def test_validate_observation_dates_rejects_datetime_values() -> None:
    with pytest.raises(TypeError, match=r"observation_dates must contain datetime\.date"):
        validate_observation_dates(
            [datetime(2026, 1, 1, 12, 30)],
            1,
            length_label="APL/HPL",
        )


def test_select_recent_observation_window_defaults_without_calendar() -> None:
    dates = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 5),
    )

    window = select_recent_observation_window(
        dates,
        2,
        validation_label="PLA",
    )

    assert window.observation_dates == (date(2026, 1, 2), date(2026, 1, 5))
    assert window.calendar_basis == ObservationWindowBasis.OBSERVATION_COUNT_PROXY
    assert window.official_holiday_count == 0


def test_select_recent_observation_window_records_calendar_metadata() -> None:
    dates = (
        date(2025, 12, 31),
        date(2026, 1, 2),
        date(2026, 1, 5),
    )
    calendar = BusinessCalendar(
        business_dates=dates,
        official_holidays=(date(2026, 1, 1),),
        source="FED",
        version="2026.1",
    )

    window = select_recent_observation_window(
        dates,
        3,
        calendar=calendar,
        validation_label="backtesting",
    )

    assert window.observation_dates == dates
    assert window.calendar_source == "FED"
    assert window.calendar_version == "2026.1"
    assert window.calendar_basis == ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS
    assert window.official_holiday_count == 1


def test_select_recent_observation_window_rejects_calendar_without_dates() -> None:
    calendar = BusinessCalendar(
        business_dates=(date(2026, 1, 2),),
        source="FED",
        version="2026.1",
    )

    with pytest.raises(ValueError, match="observation_dates are required"):
        select_recent_observation_window(
            None,
            1,
            calendar=calendar,
            validation_label="PLA",
        )


def test_select_recent_observation_window_rejects_calendar_mismatch() -> None:
    calendar = BusinessCalendar(
        business_dates=(date(2026, 1, 2), date(2026, 1, 5)),
        source="FED",
        version="2026.1",
    )

    with pytest.raises(ValueError, match="PLA window dates"):
        select_recent_observation_window(
            (date(2026, 1, 2), date(2026, 1, 6)),
            2,
            calendar=calendar,
            validation_label="PLA",
        )
