"""Tests for dependency-free business-calendar contracts."""

from datetime import date, datetime, timedelta

import pytest

from frtb_ima.calendar import BusinessCalendar, ObservationWindow, ObservationWindowBasis


def _weekdays(start: date, end: date, holidays: set[date] | None = None) -> tuple[date, ...]:
    holidays = set() if holidays is None else holidays
    result: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            result.append(current)
        current += timedelta(days=1)
    return tuple(result)


def test_exact_twelve_month_window_handles_leap_year_boundary() -> None:
    holidays = {date(2024, 12, 25)}
    calendar = BusinessCalendar(
        business_dates=_weekdays(date(2024, 2, 29), date(2025, 2, 28), holidays),
        official_holidays=tuple(holidays),
        source="FED",
        version="2026.1",
    )

    window = calendar.exact_twelve_month_window(date(2025, 2, 28))

    assert window.start_date == date(2024, 2, 29)
    assert window.end_date == date(2025, 2, 28)
    assert window.basis == ObservationWindowBasis.EXACT_TWELVE_MONTH_BUSINESS_CALENDAR
    assert window.official_holiday_count == 1
    assert window.as_dict()["calendar_source"] == "FED"


def test_calendar_rejects_duplicate_dates_and_business_holiday_overlap() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BusinessCalendar(
            business_dates=(date(2025, 1, 2), date(2025, 1, 2)),
            source="FED",
            version="2026.1",
        )
    with pytest.raises(ValueError, match="disjoint"):
        BusinessCalendar(
            business_dates=(date(2025, 1, 2),),
            official_holidays=(date(2025, 1, 2),),
            source="FED",
            version="2026.1",
        )


def test_calendar_detects_missing_business_dates() -> None:
    calendar = BusinessCalendar(
        business_dates=(date(2025, 1, 2), date(2025, 1, 6)),
        source="FED",
        version="2026.1",
    )

    with pytest.raises(ValueError, match="missing business dates"):
        calendar.window(
            date(2025, 1, 2),
            date(2025, 1, 6),
            basis=ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
        )

    window = calendar.window(
        date(2025, 1, 2),
        date(2025, 1, 6),
        basis=ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
        require_complete_weekdays=False,
    )
    assert window.missing_business_dates == (date(2025, 1, 3),)


def test_shifted_observation_period_requires_reason() -> None:
    calendar = BusinessCalendar(
        business_dates=_weekdays(date(2024, 1, 1), date(2025, 1, 31)),
        source="FED",
        version="2026.1",
    )

    with pytest.raises(ValueError, match="shift_reason"):
        calendar.exact_twelve_month_window(
            date(2025, 1, 31),
            shifted_start_date=date(2024, 1, 15),
            shifted_end_date=date(2025, 1, 14),
        )

    window = calendar.exact_twelve_month_window(
        date(2025, 1, 31),
        shifted_start_date=date(2024, 1, 15),
        shifted_end_date=date(2025, 1, 14),
        shift_reason="Policy-approved delayed close calendar",
    )

    assert window.basis == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR
    assert window.shift_reason == "Policy-approved delayed close calendar"


def test_calendar_rejects_invalid_metadata_and_weekend_configuration() -> None:
    with pytest.raises(ValueError, match="source"):
        BusinessCalendar(
            business_dates=(date(2025, 1, 2),),
            version="2026.1",
        )
    with pytest.raises(ValueError, match="version"):
        BusinessCalendar(
            business_dates=(date(2025, 1, 2),),
            source="FED",
        )
    with pytest.raises(ValueError, match="weekend_weekdays"):
        BusinessCalendar(
            business_dates=(date(2025, 1, 2),),
            source="FED",
            version="2026.1",
            weekend_weekdays=(7,),
        )
    with pytest.raises(TypeError, match=r"datetime\.date"):
        BusinessCalendar(
            business_dates=(datetime(2025, 1, 2, 12, 0),),  # type: ignore[arg-type]
            source="FED",
            version="2026.1",
        )


def test_calendar_window_methods_validate_dates_and_available_history() -> None:
    calendar = BusinessCalendar(
        business_dates=(date(2025, 1, 2), date(2025, 1, 3)),
        source="FED",
        version="2026.1",
    )

    with pytest.raises(TypeError, match="as_of_date"):
        calendar.exact_twelve_month_window("2025-01-03")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="supplied together"):
        calendar.exact_twelve_month_window(
            date(2025, 1, 3),
            shifted_start_date=date(2025, 1, 2),
        )
    with pytest.raises(ValueError, match="positive"):
        calendar.most_recent_business_days(0, as_of_date=date(2025, 1, 3))
    with pytest.raises(TypeError, match="as_of_date"):
        calendar.most_recent_business_days(1, as_of_date="2025-01-03")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="fewer than 3"):
        calendar.most_recent_business_days(3, as_of_date=date(2025, 1, 3))
    with pytest.raises(TypeError, match="window dates"):
        calendar.window(
            "2025-01-02",  # type: ignore[arg-type]
            date(2025, 1, 3),
            basis=ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
        )
    with pytest.raises(ValueError, match="after end_date"):
        calendar.window(
            date(2025, 1, 3),
            date(2025, 1, 2),
            basis=ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
        )
    with pytest.raises(ValueError, match="no business dates"):
        calendar.window(
            date(2025, 1, 4),
            date(2025, 1, 5),
            basis=ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
        )


def test_observation_window_validates_direct_construction() -> None:
    base_kwargs = {
        "start_date": date(2025, 1, 2),
        "end_date": date(2025, 1, 3),
        "business_dates": (date(2025, 1, 2),),
        "official_holidays": (date(2025, 1, 3),),
        "calendar_source": "FED",
        "calendar_version": "2026.1",
        "basis": ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
    }

    with pytest.raises(ValueError, match="after end_date"):
        ObservationWindow(**(base_kwargs | {"start_date": date(2025, 1, 4)}))
    with pytest.raises(ValueError, match="calendar_source"):
        ObservationWindow(**(base_kwargs | {"calendar_source": ""}))
    with pytest.raises(ValueError, match="calendar_version"):
        ObservationWindow(**(base_kwargs | {"calendar_version": ""}))
    with pytest.raises(ValueError, match="inside the window"):
        ObservationWindow(**(base_kwargs | {"business_dates": (date(2025, 1, 4),)}))
    with pytest.raises(ValueError, match="official_holidays must be inside"):
        ObservationWindow(**(base_kwargs | {"official_holidays": (date(2025, 1, 4),)}))
    with pytest.raises(ValueError, match="disjoint"):
        ObservationWindow(**(base_kwargs | {"official_holidays": (date(2025, 1, 2),)}))
    with pytest.raises(ValueError, match="only valid"):
        ObservationWindow(**(base_kwargs | {"shift_reason": "not shifted"}))
