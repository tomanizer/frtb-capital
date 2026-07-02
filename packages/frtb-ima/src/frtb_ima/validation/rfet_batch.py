"""RFET columnar batch assessment stage."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np
import numpy.typing as npt

from frtb_ima._array_utils import date_from_datetime64 as _date_from_datetime64
from frtb_ima._array_utils import readonly_date_array as _readonly_date_array
from frtb_ima._array_utils import readonly_string_array as _readonly_string_array
from frtb_ima._array_utils import validate_equal_lengths as _validate_equal_lengths
from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import (
    RFETNewIssuanceEvidence,
    RiskFactorDefinition,
)
from frtb_ima.data_models import RealPriceObservation
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


def _date64_set(values: Iterable[date]) -> frozenset[np.datetime64]:
    return frozenset(np.datetime64(item, "D") for item in values)


BooleanArray = npt.NDArray[np.bool_]
DateArray = npt.NDArray[np.datetime64]
DatetimeArray = npt.NDArray[np.datetime64]
StringArray = npt.NDArray[np.str_]


@dataclass(frozen=True)
class RFETObservationBatch:
    """
    Columnar RFET real-price observations for high-volume IMA handoffs.

    This batch owns the accepted observation columns from Arrow ingestion. RFET
    assessment can consume it directly and only materialize ``RealPriceObservation``
    objects for excluded rows that need to appear in the audit trail.
    """

    risk_factor_names: StringArray
    observation_dates: DateArray
    sources: StringArray
    vendor_ids: StringArray
    venues: StringArray
    feeds: StringArray
    observation_timestamps: DatetimeArray
    date_normalization_evidence: StringArray
    verifiable: BooleanArray
    verifiability_reasons: StringArray
    data_pool_ids: StringArray
    vendor_audit_evidence_ids: StringArray
    source_row_ids: StringArray
    observation_time_series_ids: StringArray
    source_hash: str | None = None
    handoff_hash: str | None = None
    input_hash: str = ""

    def __post_init__(self) -> None:
        risk_factor_names = _readonly_string_array(self.risk_factor_names, "risk_factor_names")
        observation_dates = _readonly_date_array(self.observation_dates, "observation_dates")
        sources = _readonly_string_array(self.sources, "sources")
        vendor_ids = _readonly_string_array(self.vendor_ids, "vendor_ids")
        venues = _readonly_string_array(self.venues, "venues")
        feeds = _readonly_string_array(self.feeds, "feeds")
        observation_timestamps = _readonly_datetime_array(
            self.observation_timestamps,
            "observation_timestamps",
        )
        date_normalization_evidence = _readonly_string_array(
            self.date_normalization_evidence,
            "date_normalization_evidence",
        )
        verifiable = _readonly_bool_array(self.verifiable, "verifiable")
        verifiability_reasons = _readonly_string_array(
            self.verifiability_reasons,
            "verifiability_reasons",
        )
        data_pool_ids = _readonly_string_array(self.data_pool_ids, "data_pool_ids")
        vendor_audit_evidence_ids = _readonly_string_array(
            self.vendor_audit_evidence_ids,
            "vendor_audit_evidence_ids",
        )
        source_row_ids = _readonly_string_array(self.source_row_ids, "source_row_ids")
        observation_time_series_ids = _readonly_string_array(
            self.observation_time_series_ids,
            "observation_time_series_ids",
        )
        _validate_equal_lengths(
            "RFET observation batch",
            risk_factor_names,
            observation_dates,
            sources,
            vendor_ids,
            venues,
            feeds,
            observation_timestamps,
            date_normalization_evidence,
            verifiable,
            verifiability_reasons,
            data_pool_ids,
            vendor_audit_evidence_ids,
            source_row_ids,
            observation_time_series_ids,
        )
        if risk_factor_names.size == 0:
            raise ValueError("RFET observation batch must be non-empty")
        if bool(np.any(risk_factor_names == "")):
            raise ValueError("risk_factor_names cannot contain empty values")

        object.__setattr__(self, "risk_factor_names", risk_factor_names)
        object.__setattr__(self, "observation_dates", observation_dates)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "vendor_ids", vendor_ids)
        object.__setattr__(self, "venues", venues)
        object.__setattr__(self, "feeds", feeds)
        object.__setattr__(self, "observation_timestamps", observation_timestamps)
        object.__setattr__(
            self,
            "date_normalization_evidence",
            date_normalization_evidence,
        )
        object.__setattr__(self, "verifiable", verifiable)
        object.__setattr__(self, "verifiability_reasons", verifiability_reasons)
        object.__setattr__(self, "data_pool_ids", data_pool_ids)
        object.__setattr__(self, "vendor_audit_evidence_ids", vendor_audit_evidence_ids)
        object.__setattr__(self, "source_row_ids", source_row_ids)
        object.__setattr__(
            self,
            "observation_time_series_ids",
            observation_time_series_ids,
        )
        if not self.input_hash:
            object.__setattr__(self, "input_hash", input_hash_for_rfet_observation_batch(self))

    @property
    def observation_count(self) -> int:
        """Number of accepted RFET observation rows in the batch.
        Returns
        -------
        int
            Result of the operation.
        """

        return int(self.risk_factor_names.size)

    def indices_for_risk_factor(self, risk_factor_name: str) -> npt.NDArray[np.int_]:
        """Return accepted row indices for one risk factor without materializing rows.
        Parameters
        ----------
        risk_factor_name : str
            Risk factor name.

        Returns
        -------
        npt.NDArray[np.int_]
            Result of the operation.
        """

        return np.nonzero(self.risk_factor_names == risk_factor_name)[0]

    def to_observations(self) -> tuple[RealPriceObservation, ...]:
        """Materialize compatibility dataclasses in batch order.

        High-volume RFET assessment should use ``assess_rfet_observation_batch``.
        Returns
        -------
        tuple[RealPriceObservation, ...]
            Result of the operation.
        """

        return tuple(_observation_at(self, index) for index in range(self.observation_count))


def input_hash_for_rfet_observation_batch(batch: RFETObservationBatch) -> str:
    """Return a stable audit hash for a columnar RFET observation batch.
    Parameters
    ----------
    batch : RFETObservationBatch
        Batch.

    Returns
    -------
    str
        Result of the operation.
    """

    return compute_inputs_hash(
        risk_factor_names=batch.risk_factor_names,
        observation_dates=batch.observation_dates,
        sources=batch.sources,
        vendor_ids=batch.vendor_ids,
        venues=batch.venues,
        feeds=batch.feeds,
        observation_timestamps=batch.observation_timestamps,
        date_normalization_evidence=batch.date_normalization_evidence,
        verifiable=batch.verifiable,
        verifiability_reasons=batch.verifiability_reasons,
        data_pool_ids=batch.data_pool_ids,
        vendor_audit_evidence_ids=batch.vendor_audit_evidence_ids,
        source_row_ids=batch.source_row_ids,
        observation_time_series_ids=batch.observation_time_series_ids,
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
    )


def _readonly_bool_array(values: object, field_name: str) -> BooleanArray:
    array = np.array(values, dtype=np.bool_, copy=True)
    if array.ndim != 1:
        raise ValueError(f"{field_name} must be one-dimensional")
    array.flags.writeable = False
    return array


def _readonly_datetime_array(values: object, field_name: str) -> DatetimeArray:
    array = np.array(values, dtype="datetime64[us]", copy=True)
    if array.ndim != 1:
        raise ValueError(f"{field_name} must be one-dimensional")
    array.flags.writeable = False
    return array


def _datetime_from_datetime64(value: np.datetime64) -> datetime | None:
    if np.isnat(value):
        return None
    raw = value.astype("datetime64[us]").item()
    if not isinstance(raw, datetime):
        raise TypeError("observation timestamp did not convert to datetime")
    if raw.tzinfo is None:
        return raw.replace(tzinfo=UTC)
    return raw


def _observation_at(batch: RFETObservationBatch, index: int) -> RealPriceObservation:
    return RealPriceObservation(
        risk_factor_name=str(batch.risk_factor_names[index]),
        observation_date=_date_from_datetime64(
            batch.observation_dates[index],
            "observation date",
        ),
        source=str(batch.sources[index]),
        vendor_id=str(batch.vendor_ids[index]),
        venue=str(batch.venues[index]),
        feed=str(batch.feeds[index]),
        observation_timestamp=_datetime_from_datetime64(batch.observation_timestamps[index]),
        date_normalization_evidence=str(batch.date_normalization_evidence[index]),
        verifiable=bool(batch.verifiable[index]),
        verifiability_reason=str(batch.verifiability_reasons[index]),
        data_pool_id=str(batch.data_pool_ids[index]),
        vendor_audit_evidence_id=str(batch.vendor_audit_evidence_ids[index]),
        source_row_id=str(batch.source_row_ids[index]),
    )
