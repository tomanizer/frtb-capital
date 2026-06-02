from __future__ import annotations

from datetime import date, datetime

import pytest

from frtb_ima._observation_utils import validate_observation_dates


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
