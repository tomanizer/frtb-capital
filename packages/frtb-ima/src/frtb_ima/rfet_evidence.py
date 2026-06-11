"""
RFET evidence assessment.

This module evaluates real-price evidence packages before the simpler RFET
classification functions in ``rfet.py`` are used. It keeps an audit trail of
which observations counted, which were excluded, and why.

Regulatory traceability:
    Supports NPR-MR-RFET-001 through NPR-MR-RFET-003 in
    docs/requirements/NPR_2_0_MARKET_RISK.yml.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
import numpy.typing as npt

from frtb_ima._array_utils import date_from_datetime64 as _date_from_datetime64
from frtb_ima._array_utils import readonly_date_array as _readonly_date_array
from frtb_ima._array_utils import readonly_string_array as _readonly_string_array
from frtb_ima._array_utils import validate_equal_lengths as _validate_equal_lengths
from frtb_ima.assembly.rfet import RFETEvidenceAssessment as RFETEvidenceAssessment
from frtb_ima.assembly.rfet import _count_pairs as _count_pairs
from frtb_ima.assembly.rfet import _exclusion_count_pairs as _exclusion_count_pairs
from frtb_ima.assembly.rfet import (
    _new_issuance_policy_basis as _new_issuance_policy_basis,
)
from frtb_ima.assembly.rfet import _status_from_tests as _status_from_tests
from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import (
    RFETDataPoolEvidence,
    RFETEvidence,
    RFETNewIssuanceEvidence,
    RFETRepresentativenessEvidence,
    RiskFactorDefinition,
)
from frtb_ima.data_models import RealPriceObservation
from frtb_ima.regimes import RegulatoryPolicy
from frtb_ima.validation.rfet_batch import (
    _rfet_batch_observation_window,
    _rfet_batch_required_observations,
)
from frtb_ima.validation.rfet_qualitative import (
    _representativeness_result_from_controls,
    _rfet_qualitative_stage,
)
from frtb_ima.validation.rfet_quantitative import (
    RFETExclusionReason as RFETExclusionReason,
)
from frtb_ima.validation.rfet_quantitative import (
    RFETObservationExclusion as RFETObservationExclusion,
)
from frtb_ima.validation.rfet_quantitative import (
    _rfet_quantitative_stage,
)
from frtb_ima.validation.rfet_thresholds import (
    _rfet_required_observations,
)
from frtb_ima.validation.rfet_thresholds import (
    base_required_observation_count as base_required_observation_count,
)
from frtb_ima.validation.rfet_thresholds import (
    prorated_required_observation_count as prorated_required_observation_count,
)
from frtb_ima.validation.rfet_window import (
    _rfet_observation_window as _rfet_observation_window,
)
from frtb_ima.validation.rfet_window import (
    _RFETObservationWindow as _RFETObservationWindow,
)

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
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
    )


def assess_rfet_observation_batch(
    risk_factor: RiskFactorDefinition,
    observations: RFETObservationBatch,
    policy: RegulatoryPolicy,
    *,
    as_of_date: date,
    qualitative_pass: bool,
    bucket_id: str = "",
    representativeness: Sequence[RFETRepresentativenessEvidence] = (),
    data_pools: Sequence[RFETDataPoolEvidence] = (),
    new_issuance: RFETNewIssuanceEvidence | None = None,
    issue_date: date | None = None,
    allow_new_issuance_prorating: bool = False,
    require_source: bool = True,
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> RFETEvidenceAssessment:
    """Assess one risk factor's RFET observations from a columnar batch.

    The regulatory decision logic mirrors ``assess_rfet_evidence`` while
    avoiding accepted-row ``RealPriceObservation`` construction on the fast path.
    Excluded rows are materialized only because the existing audit result embeds
    the excluded observation details.
    Parameters
    ----------
    risk_factor : RiskFactorDefinition
        Risk factor.
    observations : RFETObservationBatch
        Observations.
    policy : RegulatoryPolicy
        Policy.
    as_of_date : date
        As of date.
    qualitative_pass : bool
        Qualitative pass.
    bucket_id : str, optional
        Bucket id.
    representativeness : Sequence[RFETRepresentativenessEvidence], optional
        Representativeness.
    data_pools : Sequence[RFETDataPoolEvidence], optional
        Data pools.
    new_issuance : RFETNewIssuanceEvidence | None, optional
        New issuance.
    issue_date : date | None, optional
        Issue date.
    allow_new_issuance_prorating : bool, optional
        Allow new issuance prorating.
    require_source : bool, optional
        Require source.
    calendar : BusinessCalendar | None, optional
        Calendar.
    shifted_start_date : date | None, optional
        Shifted start date.
    shifted_end_date : date | None, optional
        Shifted end date.
    shift_reason : str, optional
        Shift reason.

    Returns
    -------
    RFETEvidenceAssessment
        Result of the operation.
    """

    if type(as_of_date) is not date:
        raise TypeError("as_of_date must be a datetime.date")
    if not isinstance(qualitative_pass, bool):
        raise TypeError("qualitative_pass must be a bool")

    window = _rfet_batch_observation_window(
        as_of_date,
        policy,
        calendar=calendar,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
    )
    required_observations = _rfet_batch_required_observations(
        risk_factor,
        policy,
        window,
        as_of_date=as_of_date,
        new_issuance=new_issuance,
        issue_date=issue_date,
        allow_new_issuance_prorating=allow_new_issuance_prorating,
    )

    bucket_representative, representative_items = _representativeness_result_from_controls(
        risk_factor,
        bucket_id,
        representativeness,
    )
    lookback_start64 = np.datetime64(window.lookback_start, "D")
    lookback_end64 = np.datetime64(window.lookback_end, "D")
    as_of64 = np.datetime64(as_of_date, "D")
    indices = observations.indices_for_risk_factor(risk_factor.name)
    if indices.size:
        ordered_indices = indices[
            np.argsort(observations.observation_dates[indices], kind="stable")
        ]
    else:
        ordered_indices = indices

    seen_dates: set[np.datetime64] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    eligible_dates: list[date] = []
    eligible_sources: set[str] = set()
    eligible_vendors: list[str] = []
    exclusions: list[RFETObservationExclusion] = []

    for index_value in ordered_indices:
        index = int(index_value)
        observation_date = observations.observation_dates[index]
        reason: RFETExclusionReason | None = None
        lineage_key = _lineage_key_from_batch(observations, index)
        if observation_date > as_of64:
            reason = RFETExclusionReason.FUTURE_OBSERVATION
        elif observation_date < lookback_start64 or observation_date > lookback_end64:
            reason = RFETExclusionReason.OUTSIDE_LOOKBACK
        elif observation_date in window.official_holidays:
            reason = RFETExclusionReason.OFFICIAL_HOLIDAY
        elif window.business_dates is not None and observation_date not in window.business_dates:
            reason = RFETExclusionReason.NON_BUSINESS_DATE
        elif require_source and not observations.sources[index]:
            reason = RFETExclusionReason.MISSING_SOURCE
        elif not bool(observations.verifiable[index]):
            reason = RFETExclusionReason.UNVERIFIABLE_PRICE
        elif _requires_date_normalization_evidence_batch(observations, index):
            reason = RFETExclusionReason.MISSING_DATE_NORMALIZATION_EVIDENCE
        elif not _has_vendor_audit_evidence_batch(observations, index, data_pools):
            reason = RFETExclusionReason.MISSING_VENDOR_AUDIT_EVIDENCE
        elif not bucket_representative:
            reason = (
                RFETExclusionReason.NON_REPRESENTATIVE_EVIDENCE
                if representative_items
                else RFETExclusionReason.NON_REPRESENTATIVE_BUCKET
            )
        elif lineage_key in seen_lineage_keys:
            reason = RFETExclusionReason.DUPLICATE_SOURCE_VENDOR
        elif observation_date in seen_dates:
            reason = RFETExclusionReason.DUPLICATE_DATE

        if reason is not None:
            exclusions.append(
                RFETObservationExclusion(_observation_at(observations, index), reason)
            )
            continue

        seen_lineage_keys.add(lineage_key)
        seen_dates.add(observation_date)
        eligible_dates.append(_date_from_datetime64(observation_date, "observation date"))
        source = str(observations.sources[index])
        if source:
            eligible_sources.add(source)
        vendor_id = str(observations.vendor_ids[index])
        if vendor_id:
            eligible_vendors.append(vendor_id)

    eligible_count = len(eligible_dates)
    quantitative_pass = eligible_count >= required_observations.required
    status = _status_from_tests(qualitative_pass, quantitative_pass)

    return RFETEvidenceAssessment(
        risk_factor_name=risk_factor.name,
        as_of_date=as_of_date,
        lookback_start=window.lookback_start,
        base_required_observations=required_observations.base_required,
        required_observations=required_observations.required,
        eligible_observation_count=eligible_count,
        eligible_observation_dates=tuple(eligible_dates),
        source_count=len(eligible_sources),
        qualitative_pass=qualitative_pass,
        quantitative_pass=quantitative_pass,
        bucket_representative=bucket_representative,
        new_issuance_prorated=required_observations.new_issuance_prorated,
        modellability_status=status,
        lookback_basis=window.lookback_basis,
        calendar_source=window.calendar_source,
        calendar_version=window.calendar_version,
        official_holiday_count=window.official_holiday_count,
        missing_business_dates=window.missing_business_dates,
        shift_reason=shift_reason
        if window.lookback_basis
        == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR.value
        else "",
        source_counts=_count_pairs(str(observations.sources[index]) for index in ordered_indices),
        vendor_counts=_count_pairs(eligible_vendors),
        exclusion_counts=_exclusion_count_pairs(exclusions),
        bucket_counts=_count_pairs(
            item
            for item in (
                bucket_id,
                *(representative.bucket_id for representative in representative_items),
            )
            if item
        ),
        representative_methodology_counts=_count_pairs(
            representative.methodology for representative in representative_items
        ),
        data_pool_count=len(data_pools),
        vendor_audit_evidence_count=len(
            {
                item
                for item in (
                    *(pool.independent_audit_evidence_id for pool in data_pools),
                    *(
                        str(observations.vendor_audit_evidence_ids[index])
                        for index in ordered_indices
                    ),
                )
                if item
            }
        ),
        new_issuance_policy_basis=_new_issuance_policy_basis(new_issuance),
        exclusions=tuple(exclusions),
    )


def assess_rfet_evidence(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
    policy: RegulatoryPolicy,
    *,
    issue_date: date | None = None,
    allow_new_issuance_prorating: bool = False,
    require_source: bool = True,
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> RFETEvidenceAssessment:
    """Assess real-price evidence for one risk factor under a policy.

    Counting rules implemented here:
    - observations must fall within the policy lookback window;
    - observations after ``as_of_date`` do not count;
    - at most one observation counts per calendar date;
    - evidence must match the risk factor's bucket or explicit representativeness checks;
    - source lineage is required by default.
    Parameters
    ----------
    risk_factor : RiskFactorDefinition
        Risk factor.
    evidence : RFETEvidence
        Evidence.
    policy : RegulatoryPolicy
        Policy.
    issue_date : date | None, optional
        Issue date.
    allow_new_issuance_prorating : bool, optional
        Allow new issuance prorating.
    require_source : bool, optional
        Require source.
    calendar : BusinessCalendar | None, optional
        Calendar.
    shifted_start_date : date | None, optional
        Shifted start date.
    shifted_end_date : date | None, optional
        Shifted end date.
    shift_reason : str, optional
        Shift reason.

    Returns
    -------
    RFETEvidenceAssessment
        Result of the operation.
    """
    if risk_factor.name != evidence.risk_factor_name:
        raise ValueError("risk_factor and evidence names must match")

    window = _rfet_observation_window(
        evidence.as_of_date,
        policy,
        calendar=calendar,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
    )
    required_observations = _rfet_required_observations(
        risk_factor,
        evidence,
        policy,
        window,
        issue_date=issue_date,
        allow_new_issuance_prorating=allow_new_issuance_prorating,
    )
    qualitative = _rfet_qualitative_stage(risk_factor, evidence)
    quantitative = _rfet_quantitative_stage(
        evidence,
        window,
        qualitative,
        require_source=require_source,
    )

    eligible_count = len(quantitative.eligible_dates)
    quantitative_pass = eligible_count >= required_observations.required
    status = _status_from_tests(qualitative.qualitative_pass, quantitative_pass)

    return RFETEvidenceAssessment(
        risk_factor_name=risk_factor.name,
        as_of_date=evidence.as_of_date,
        lookback_start=window.lookback_start,
        base_required_observations=required_observations.base_required,
        required_observations=required_observations.required,
        eligible_observation_count=eligible_count,
        eligible_observation_dates=quantitative.eligible_dates,
        source_count=len(quantitative.eligible_sources),
        qualitative_pass=qualitative.qualitative_pass,
        quantitative_pass=quantitative_pass,
        bucket_representative=qualitative.bucket_representative,
        new_issuance_prorated=required_observations.new_issuance_prorated,
        modellability_status=status,
        lookback_basis=window.lookback_basis,
        calendar_source=window.calendar_source,
        calendar_version=window.calendar_version,
        official_holiday_count=window.official_holiday_count,
        missing_business_dates=window.missing_business_dates,
        shift_reason=shift_reason
        if window.lookback_basis
        == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR.value
        else "",
        source_counts=_count_pairs(observation.source for observation in evidence.observations),
        vendor_counts=_count_pairs(quantitative.eligible_vendors),
        exclusion_counts=_exclusion_count_pairs(quantitative.exclusions),
        bucket_counts=_count_pairs(
            item
            for item in (
                evidence.bucket_id,
                *(representative.bucket_id for representative in qualitative.representativeness),
            )
            if item
        ),
        representative_methodology_counts=_count_pairs(
            representative.methodology for representative in qualitative.representativeness
        ),
        data_pool_count=len(evidence.data_pools),
        vendor_audit_evidence_count=len(
            {
                item
                for item in (
                    *(pool.independent_audit_evidence_id for pool in evidence.data_pools),
                    *(
                        observation.vendor_audit_evidence_id
                        for observation in evidence.observations
                    ),
                )
                if item
            }
        ),
        new_issuance_policy_basis=_new_issuance_policy_basis(evidence.new_issuance),
        exclusions=quantitative.exclusions,
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
    )


def _lineage_key_from_batch(batch: RFETObservationBatch, index: int) -> tuple[object, ...]:
    return (
        batch.observation_dates[index],
        str(batch.sources[index]),
        str(batch.vendor_ids[index]),
        str(batch.venues[index]),
        str(batch.feeds[index]),
        str(batch.data_pool_ids[index]),
    )


def _requires_date_normalization_evidence_batch(
    batch: RFETObservationBatch,
    index: int,
) -> bool:
    timestamp = batch.observation_timestamps[index]
    return (
        not np.isnat(timestamp)
        and timestamp.astype("datetime64[D]") != batch.observation_dates[index]
        and not str(batch.date_normalization_evidence[index])
    )


def _has_vendor_audit_evidence_batch(
    batch: RFETObservationBatch,
    index: int,
    data_pools: Sequence[RFETDataPoolEvidence],
) -> bool:
    vendor_id = str(batch.vendor_ids[index])
    if not vendor_id:
        return True
    if str(batch.vendor_audit_evidence_ids[index]):
        return True
    data_pool_id = str(batch.data_pool_ids[index])
    for pool in data_pools:
        if data_pool_id and pool.pool_id == data_pool_id:
            return True
        if pool.vendor_id == vendor_id:
            return True
    return False
