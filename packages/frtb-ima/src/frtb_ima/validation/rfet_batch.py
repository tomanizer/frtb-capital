"""RFET columnar batch assessment setup stage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import RFETNewIssuanceEvidence, RiskFactorDefinition
from frtb_ima.regimes import RegulatoryPolicy
from frtb_ima.validation.rfet_thresholds import (
    _RFETRequiredObservations,
    base_required_observation_count,
    prorated_required_observation_count,
)


@dataclass(frozen=True)
class _RFETBatchObservationWindow:
    lookback_start: date
    lookback_end: date
    lookback_basis: str
    calendar_source: str
    calendar_version: str
    official_holiday_count: int
    missing_business_dates: tuple[date, ...]
    business_dates: frozenset[np.datetime64] | None
    official_holidays: frozenset[np.datetime64]


def _rfet_batch_observation_window(
    as_of_date: date,
    policy: RegulatoryPolicy,
    *,
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> _RFETBatchObservationWindow:
    if calendar is None:
        return _RFETBatchObservationWindow(
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
    return _RFETBatchObservationWindow(
        lookback_start=window.start_date,
        lookback_end=window.end_date,
        lookback_basis=window.basis.value,
        calendar_source=window.calendar_source,
        calendar_version=window.calendar_version,
        official_holiday_count=window.official_holiday_count,
        missing_business_dates=window.missing_business_dates,
        business_dates=_date64_set(window.business_dates),
        official_holidays=_date64_set(window.official_holidays),
    )


def _rfet_batch_required_observations(
    risk_factor: RiskFactorDefinition,
    policy: RegulatoryPolicy,
    window: _RFETBatchObservationWindow,
    *,
    as_of_date: date,
    new_issuance: RFETNewIssuanceEvidence | None = None,
    issue_date: date | None = None,
    allow_new_issuance_prorating: bool = False,
) -> _RFETRequiredObservations:
    base_required = base_required_observation_count(risk_factor, policy)
    effective_issue_date = new_issuance.issue_date if new_issuance is not None else issue_date
    prorating_approved = (
        new_issuance is not None and new_issuance.prorating_approved
    ) or allow_new_issuance_prorating
    if effective_issue_date is None or not prorating_approved:
        return _RFETRequiredObservations(
            base_required=base_required,
            required=base_required,
            new_issuance_prorated=False,
        )

    required = prorated_required_observation_count(
        base_required,
        lookback_start=window.lookback_start,
        as_of_date=as_of_date,
        issue_date=effective_issue_date,
    )
    return _RFETRequiredObservations(
        base_required=base_required,
        required=required,
        new_issuance_prorated=required != base_required,
    )


def _date64_set(values: tuple[date, ...]) -> frozenset[np.datetime64]:
    return frozenset(np.datetime64(item, "D") for item in values)
