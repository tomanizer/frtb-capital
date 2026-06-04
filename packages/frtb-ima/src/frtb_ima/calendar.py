"""
Dependency-free business-calendar contracts for dated observation windows.

The package does not source holiday calendars. Callers supply authoritative
business dates, official holidays, and calendar source/version metadata; the
calculation layer validates and records the resulting observation windows.

Regulatory traceability:
    Supports RFET, PLA, backtesting, and stress-period dated observation-window
    evidence in docs/requirements/NPR_2_0_MARKET_RISK.yml.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from itertools import pairwise


class ObservationWindowBasis(StrEnum):
    """How a dated observation window was selected."""

    EXACT_TWELVE_MONTH_BUSINESS_CALENDAR = "EXACT_TWELVE_MONTH_BUSINESS_CALENDAR"
    SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR = "SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR"
    MOST_RECENT_BUSINESS_DAYS = "MOST_RECENT_BUSINESS_DAYS"
    OBSERVATION_COUNT_PROXY = "OBSERVATION_COUNT_PROXY"


@dataclass(frozen=True)
class ObservationWindow:
    """Business-calendar evidence for one selected observation window."""

    start_date: date
    end_date: date
    business_dates: tuple[date, ...]
    official_holidays: tuple[date, ...]
    calendar_source: str
    calendar_version: str
    basis: ObservationWindowBasis
    shift_reason: str = ""
    missing_business_dates: tuple[date, ...] = ()

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        if not self.calendar_source:
            raise ValueError("calendar_source must be non-empty")
        if not self.calendar_version:
            raise ValueError("calendar_version must be non-empty")
        business_dates = _strictly_increasing_dates(self.business_dates, "business_dates")
        official_holidays = _strictly_increasing_dates(
            self.official_holidays,
            "official_holidays",
            allow_empty=True,
        )
        missing_business_dates = _strictly_increasing_dates(
            self.missing_business_dates,
            "missing_business_dates",
            allow_empty=True,
        )
        if any(item < self.start_date or item > self.end_date for item in business_dates):
            raise ValueError("business_dates must be inside the window")
        if any(item < self.start_date or item > self.end_date for item in official_holidays):
            raise ValueError("official_holidays must be inside the window")
        if set(business_dates) & set(official_holidays):
            raise ValueError("business_dates and official_holidays must be disjoint")
        basis = ObservationWindowBasis(self.basis)
        if basis == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR:
            if not self.shift_reason:
                raise ValueError("shift_reason is required for shifted observation windows")
        elif self.shift_reason:
            raise ValueError("shift_reason is only valid for shifted observation windows")
        object.__setattr__(self, "business_dates", business_dates)
        object.__setattr__(self, "official_holidays", official_holidays)
        object.__setattr__(self, "missing_business_dates", missing_business_dates)
        object.__setattr__(self, "basis", basis)

    @property
    def business_day_count(self) -> int:
        """Number of supplied business dates in the window.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.business_dates)

    @property
    def official_holiday_count(self) -> int:
        """Number of supplied official holidays in the window.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.official_holidays)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for audit/report outputs.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "business_day_count": self.business_day_count,
            "official_holiday_count": self.official_holiday_count,
            "calendar_source": self.calendar_source,
            "calendar_version": self.calendar_version,
            "basis": self.basis.value,
            "shift_reason": self.shift_reason,
            "official_holidays": [item.isoformat() for item in self.official_holidays],
            "missing_business_dates": [item.isoformat() for item in self.missing_business_dates],
        }


@dataclass(frozen=True)
class BusinessCalendar:
    """Caller-supplied business dates and official holidays."""

    business_dates: tuple[date, ...]
    official_holidays: tuple[date, ...] = ()
    source: str = ""
    version: str = ""
    weekend_weekdays: tuple[int, ...] = (5, 6)

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("source must be non-empty")
        if not self.version:
            raise ValueError("version must be non-empty")
        business_dates = _strictly_increasing_dates(self.business_dates, "business_dates")
        official_holidays = tuple(
            sorted(
                _unique_dates(
                    self.official_holidays,
                    "official_holidays",
                    allow_empty=True,
                )
            )
        )
        if set(business_dates) & set(official_holidays):
            raise ValueError("business_dates and official_holidays must be disjoint")
        weekend_weekdays = tuple(self.weekend_weekdays)
        if any(not isinstance(item, int) or item < 0 or item > 6 for item in weekend_weekdays):
            raise ValueError("weekend_weekdays must contain weekday integers in [0, 6]")
        object.__setattr__(self, "business_dates", business_dates)
        object.__setattr__(self, "official_holidays", official_holidays)
        object.__setattr__(self, "weekend_weekdays", weekend_weekdays)

    def exact_twelve_month_window(
        self,
        as_of_date: date,
        *,
        shifted_start_date: date | None = None,
        shifted_end_date: date | None = None,
        shift_reason: str = "",
        require_complete_weekdays: bool = True,
    ) -> ObservationWindow:
        """Return an exact 12-month business-calendar window.

        The unshifted window is ``(as_of_date - 12 months, as_of_date]``. A
        shifted period must supply both dates and a non-empty policy reason.
        Parameters
        ----------
        as_of_date : date
            As of date.
        shifted_start_date : date | None, optional
            Shifted start date.
        shifted_end_date : date | None, optional
            Shifted end date.
        shift_reason : str, optional
            Shift reason.
        require_complete_weekdays : bool, optional
            Require complete weekdays.

        Returns
        -------
        ObservationWindow
            Result of the operation.
        """
        if not isinstance(as_of_date, date):
            raise TypeError("as_of_date must be a datetime.date")
        if shifted_start_date is None and shifted_end_date is None:
            start = _add_months(as_of_date, -12) + timedelta(days=1)
            end = as_of_date
            basis = ObservationWindowBasis.EXACT_TWELVE_MONTH_BUSINESS_CALENDAR
            reason = ""
        elif shifted_start_date is not None and shifted_end_date is not None:
            start = shifted_start_date
            end = shifted_end_date
            basis = ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR
            reason = shift_reason
        else:
            raise ValueError("shifted_start_date and shifted_end_date must be supplied together")
        return self.window(
            start,
            end,
            basis=basis,
            shift_reason=reason,
            require_complete_weekdays=require_complete_weekdays,
        )

    def most_recent_business_days(
        self,
        count: int,
        *,
        as_of_date: date,
        require_complete_weekdays: bool = True,
    ) -> ObservationWindow:
        """Return the most recent ``count`` supplied business dates up to ``as_of_date``.
        Parameters
        ----------
        count : int
            Count.
        as_of_date : date
            As of date.
        require_complete_weekdays : bool, optional
            Require complete weekdays.

        Returns
        -------
        ObservationWindow
            Result of the operation.
        """
        if count <= 0:
            raise ValueError(f"count must be positive, got {count}")
        if not isinstance(as_of_date, date):
            raise TypeError("as_of_date must be a datetime.date")
        eligible = tuple(item for item in self.business_dates if item <= as_of_date)
        if len(eligible) < count:
            raise ValueError(f"calendar contains fewer than {count} business dates")
        selected = eligible[-count:]
        return self.window(
            selected[0],
            selected[-1],
            basis=ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS,
            require_complete_weekdays=require_complete_weekdays,
        )

    def window(
        self,
        start_date: date,
        end_date: date,
        *,
        basis: ObservationWindowBasis,
        shift_reason: str = "",
        require_complete_weekdays: bool = True,
    ) -> ObservationWindow:
        """Return supplied business dates and official holidays for a date range.
        Parameters
        ----------
        start_date : date
            Start date.
        end_date : date
            End date.
        basis : ObservationWindowBasis
            Basis.
        shift_reason : str, optional
            Shift reason.
        require_complete_weekdays : bool, optional
            Require complete weekdays.

        Returns
        -------
        ObservationWindow
            Result of the operation.
        """
        if not isinstance(start_date, date) or not isinstance(end_date, date):
            raise TypeError("window dates must be datetime.date values")
        if start_date > end_date:
            raise ValueError("start_date cannot be after end_date")
        business_dates = tuple(
            item for item in self.business_dates if start_date <= item <= end_date
        )
        if not business_dates:
            raise ValueError("calendar window contains no business dates")
        official_holidays = tuple(
            item for item in self.official_holidays if start_date <= item <= end_date
        )
        missing = self.missing_weekdays(start_date, end_date)
        if require_complete_weekdays and missing:
            sample = ", ".join(item.isoformat() for item in missing[:5])
            raise ValueError(f"calendar is missing business dates: {sample}")
        return ObservationWindow(
            start_date=start_date,
            end_date=end_date,
            business_dates=business_dates,
            official_holidays=official_holidays,
            calendar_source=self.source,
            calendar_version=self.version,
            basis=basis,
            shift_reason=shift_reason,
            missing_business_dates=missing,
        )

    def missing_weekdays(self, start_date: date, end_date: date) -> tuple[date, ...]:
        """Return weekday dates absent from business dates and official holidays.

        This dependency-free completeness check treats configured weekend days
        and supplied official holidays as non-business days. Callers with more
        complex exchange calendars should supply those closures as official
        holidays or disable completeness enforcement.
        Parameters
        ----------
        start_date : date
            Start date.
        end_date : date
            End date.

        Returns
        -------
        tuple[date, ...]
            Result of the operation.
        """
        business = set(self.business_dates)
        holidays = set(self.official_holidays)
        missing: list[date] = []
        current = start_date
        while current <= end_date:
            if (
                current.weekday() not in self.weekend_weekdays
                and current not in business
                and current not in holidays
            ):
                missing.append(current)
            current += timedelta(days=1)
        return tuple(missing)


def _strictly_increasing_dates(
    values: tuple[date, ...],
    name: str,
    *,
    allow_empty: bool = False,
) -> tuple[date, ...]:
    dates = _unique_dates(values, name, allow_empty=allow_empty)
    if any(left >= right for left, right in pairwise(dates)):
        raise ValueError(f"{name} must be strictly increasing")
    return dates


def _unique_dates(
    values: tuple[date, ...],
    name: str,
    *,
    allow_empty: bool = False,
) -> tuple[date, ...]:
    dates = tuple(values)
    if not dates and not allow_empty:
        raise ValueError(f"{name} must be non-empty")
    if any(type(item) is not date for item in dates):
        raise TypeError(f"{name} must contain only datetime.date values")
    if len(dates) != len(set(dates)):
        raise ValueError(f"{name} contains duplicate dates")
    return dates


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day
