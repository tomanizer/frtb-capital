"""Shared test-only helpers for IMA package tests."""

from __future__ import annotations

from datetime import date, timedelta


def business_dates(
    count: int, *, start: date, holidays: set[date] | None = None
) -> tuple[date, ...]:
    holidays = set() if holidays is None else holidays
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5 and current not in holidays:
            days.append(current)
        current += timedelta(days=1)
    return tuple(days)
