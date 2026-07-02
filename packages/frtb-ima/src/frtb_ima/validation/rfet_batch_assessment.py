"""RFET columnar batch assessment decision stage."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt

from frtb_ima._array_utils import date_from_datetime64 as _date_from_datetime64
from frtb_ima.assembly.rfet import (
    RFETEvidenceAssessment,
    _count_pairs,
    _exclusion_count_pairs,
    _new_issuance_policy_basis,
    _status_from_tests,
)
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import (
    RFETDataPoolEvidence,
    RFETNewIssuanceEvidence,
    RFETRepresentativenessEvidence,
    RiskFactorDefinition,
)
from frtb_ima.regimes import RegulatoryPolicy
from frtb_ima.validation.rfet_batch import (
    RFETObservationBatch,
    _observation_at,
    _rfet_batch_observation_window,
    _rfet_batch_required_observations,
    _RFETBatchObservationWindow,
)
from frtb_ima.validation.rfet_batch_filters import (
    _batch_exclusion_reason,
    _batch_pre_representativeness_exclusion_reason,
    _batch_vendor_audit_evidence_count,
    _lineage_key_from_batch,
)
from frtb_ima.validation.rfet_qualitative import _representativeness_result_from_controls
from frtb_ima.validation.rfet_quantitative import RFETObservationExclusion
from frtb_ima.validation.rfet_thresholds import _RFETRequiredObservations


@dataclass(frozen=True)
class _RFETBatchQuantitativeStage:
    ordered_indices: npt.NDArray[np.int_]
    eligible_dates: tuple[date, ...]
    eligible_sources: frozenset[str]
    eligible_vendors: tuple[str, ...]
    exclusions: tuple[RFETObservationExclusion, ...]
    raw_duplicate_date_count: int
    raw_duplicate_lineage_count: int


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

    Parameters
    ----------
    risk_factor, observations, policy, as_of_date, qualitative_pass
        Required RFET batch assessment inputs.
    bucket_id, representativeness, data_pools, new_issuance, issue_date,
    allow_new_issuance_prorating, require_source, calendar, shifted_start_date,
    shifted_end_date, shift_reason
        Optional evidence controls and calendar overrides.

    Returns
    -------
    RFETEvidenceAssessment
        Audit-ready RFET assessment for the selected risk factor.
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
    quantitative = _rfet_batch_quantitative_stage(
        risk_factor,
        observations,
        window,
        as_of_date=as_of_date,
        bucket_representative=bucket_representative,
        representative_items=representative_items,
        data_pools=data_pools,
        require_source=require_source,
    )
    return _build_rfet_batch_assessment(
        risk_factor,
        as_of_date=as_of_date,
        window=window,
        required_observations=required_observations,
        qualitative_pass=qualitative_pass,
        bucket_representative=bucket_representative,
        representative_items=representative_items,
        bucket_id=bucket_id,
        data_pools=data_pools,
        new_issuance=new_issuance,
        observations=observations,
        quantitative=quantitative,
        shift_reason=shift_reason,
    )


def _rfet_batch_quantitative_stage(
    risk_factor: RiskFactorDefinition,
    observations: RFETObservationBatch,
    window: _RFETBatchObservationWindow,
    *,
    as_of_date: date,
    bucket_representative: bool,
    representative_items: Sequence[RFETRepresentativenessEvidence],
    data_pools: Sequence[RFETDataPoolEvidence],
    require_source: bool,
) -> _RFETBatchQuantitativeStage:
    ordered_indices = _ordered_batch_indices(risk_factor, observations)
    lookback_start64 = np.datetime64(window.lookback_start, "D")
    lookback_end64 = np.datetime64(window.lookback_end, "D")
    as_of64 = np.datetime64(as_of_date, "D")
    seen_dates: set[np.datetime64] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    eligible_dates: list[date] = []
    eligible_sources: set[str] = set()
    eligible_vendors: list[str] = []
    exclusions: list[RFETObservationExclusion] = []
    raw_duplicate_date_count, raw_duplicate_lineage_count = _raw_batch_duplicate_counts(
        observations,
        ordered_indices,
        window,
        as_of64=as_of64,
        lookback_start64=lookback_start64,
        lookback_end64=lookback_end64,
        require_source=require_source,
        data_pools=data_pools,
    )

    for index_value in ordered_indices:
        index = int(index_value)
        observation_date = observations.observation_dates[index]
        reason = _batch_exclusion_reason(
            observations,
            index,
            observation_date=observation_date,
            as_of64=as_of64,
            lookback_start64=lookback_start64,
            lookback_end64=lookback_end64,
            window=window,
            require_source=require_source,
            bucket_representative=bucket_representative,
            representative_items=representative_items,
            seen_lineage_keys=seen_lineage_keys,
            seen_dates=seen_dates,
            data_pools=data_pools,
        )
        if reason is not None:
            exclusions.append(
                RFETObservationExclusion(_observation_at(observations, index), reason)
            )
            continue
        _record_eligible_batch_observation(
            observations,
            index,
            observation_date,
            seen_lineage_keys=seen_lineage_keys,
            seen_dates=seen_dates,
            eligible_dates=eligible_dates,
            eligible_sources=eligible_sources,
            eligible_vendors=eligible_vendors,
        )

    return _RFETBatchQuantitativeStage(
        ordered_indices=ordered_indices,
        eligible_dates=tuple(eligible_dates),
        eligible_sources=frozenset(eligible_sources),
        eligible_vendors=tuple(eligible_vendors),
        exclusions=tuple(exclusions),
        raw_duplicate_date_count=raw_duplicate_date_count,
        raw_duplicate_lineage_count=raw_duplicate_lineage_count,
    )


def _ordered_batch_indices(
    risk_factor: RiskFactorDefinition,
    observations: RFETObservationBatch,
) -> npt.NDArray[np.int_]:
    indices = observations.indices_for_risk_factor(risk_factor.name)
    if not indices.size:
        return indices
    return indices[np.argsort(observations.observation_dates[indices], kind="stable")]


def _raw_batch_duplicate_counts(
    observations: RFETObservationBatch,
    ordered_indices: npt.NDArray[np.int_],
    window: _RFETBatchObservationWindow,
    *,
    as_of64: np.datetime64,
    lookback_start64: np.datetime64,
    lookback_end64: np.datetime64,
    require_source: bool,
    data_pools: Sequence[RFETDataPoolEvidence],
) -> tuple[int, int]:
    seen_dates: set[np.datetime64] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    duplicate_dates = 0
    duplicate_lineage = 0

    for index_value in ordered_indices:
        index = int(index_value)
        observation_date = observations.observation_dates[index]
        if (
            _batch_pre_representativeness_exclusion_reason(
                observations,
                index,
                observation_date=observation_date,
                as_of64=as_of64,
                lookback_start64=lookback_start64,
                lookback_end64=lookback_end64,
                window=window,
                require_source=require_source,
                data_pools=data_pools,
            )
            is not None
        ):
            continue
        lineage_key = _lineage_key_from_batch(observations, index)
        if lineage_key in seen_lineage_keys:
            duplicate_lineage += 1
        elif observation_date in seen_dates:
            duplicate_dates += 1
        seen_lineage_keys.add(lineage_key)
        seen_dates.add(observation_date)

    return duplicate_dates, duplicate_lineage


def _record_eligible_batch_observation(
    observations: RFETObservationBatch,
    index: int,
    observation_date: np.datetime64,
    *,
    seen_lineage_keys: set[tuple[object, ...]],
    seen_dates: set[np.datetime64],
    eligible_dates: list[date],
    eligible_sources: set[str],
    eligible_vendors: list[str],
) -> None:
    seen_lineage_keys.add(_lineage_key_from_batch(observations, index))
    seen_dates.add(observation_date)
    eligible_dates.append(_date_from_datetime64(observation_date, "observation date"))
    source = str(observations.sources[index])
    if source:
        eligible_sources.add(source)
    vendor_id = str(observations.vendor_ids[index])
    if vendor_id:
        eligible_vendors.append(vendor_id)


def _build_rfet_batch_assessment(
    risk_factor: RiskFactorDefinition,
    *,
    as_of_date: date,
    window: _RFETBatchObservationWindow,
    required_observations: _RFETRequiredObservations,
    qualitative_pass: bool,
    bucket_representative: bool,
    representative_items: Sequence[RFETRepresentativenessEvidence],
    bucket_id: str,
    data_pools: Sequence[RFETDataPoolEvidence],
    new_issuance: RFETNewIssuanceEvidence | None,
    observations: RFETObservationBatch,
    quantitative: _RFETBatchQuantitativeStage,
    shift_reason: str,
) -> RFETEvidenceAssessment:
    eligible_count = len(quantitative.eligible_dates)
    quantitative_pass = eligible_count >= required_observations.required
    status = _status_from_tests(qualitative_pass, quantitative_pass)
    return RFETEvidenceAssessment(
        risk_factor_name=risk_factor.name,
        as_of_date=as_of_date,
        lookback_start=window.lookback_start,
        base_required_observations=required_observations.base_required,
        required_observations=required_observations.required,
        eligible_observation_count=eligible_count,
        eligible_observation_dates=quantitative.eligible_dates,
        source_count=len(quantitative.eligible_sources),
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
        shift_reason=_batch_shift_reason(window, shift_reason),
        source_counts=_count_pairs(
            str(observations.sources[index]) for index in quantitative.ordered_indices
        ),
        vendor_counts=_count_pairs(quantitative.eligible_vendors),
        exclusion_counts=_exclusion_count_pairs(quantitative.exclusions),
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
        raw_duplicate_date_count=quantitative.raw_duplicate_date_count,
        raw_duplicate_lineage_count=quantitative.raw_duplicate_lineage_count,
        data_pool_count=len(data_pools),
        vendor_audit_evidence_count=_batch_vendor_audit_evidence_count(
            observations,
            quantitative.ordered_indices,
            data_pools,
        ),
        new_issuance_policy_basis=_new_issuance_policy_basis(new_issuance),
        observation_time_series_ids=_unique_optional_text(
            str(observations.observation_time_series_ids[index])
            for index in quantitative.ordered_indices
        ),
        source_row_ids=_unique_optional_text(
            str(observations.source_row_ids[index]) for index in quantitative.ordered_indices
        ),
        exclusions=quantitative.exclusions,
    )


def _batch_shift_reason(window: _RFETBatchObservationWindow, shift_reason: str) -> str:
    if window.lookback_basis == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR.value:
        return shift_reason
    return ""


def _unique_optional_text(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
