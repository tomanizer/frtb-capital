"""Package-local observation validation helpers for IMA diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date


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
