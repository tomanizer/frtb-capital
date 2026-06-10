"""Baseline-versus-candidate impact analysis for DRC capital results."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from frtb_common import dataclass_as_dict
from frtb_common.attribution import ReconciliationStatus
from frtb_common.impact import CapitalImpact, ImpactMethod

from frtb_drc._identifiers import slug_path as _slug
from frtb_drc.data_models import BranchType, BucketDrc, CategoryDrc, DrcCapitalResult
from frtb_drc.validation import DrcInputError

_TOLERANCE = 1e-9
_COMPONENT = "frtb-drc"


class DrcImpactMethod(StrEnum):
    """DRC-specific method label for impact records."""

    FINITE_DIFFERENCE = "FINITE_DIFFERENCE"
    RESIDUAL = "RESIDUAL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class DrcImpactRecord:
    """Package-local explanation of one DRC baseline-vs-candidate delta.

    Parameters
    ----------
    impact_id : str
        Stable record id derived from the source level and source id.
    source_id : str
        Result graph node represented by the impact record.
    source_level : str
        Grain of the comparison, such as ``bucket``, ``category``, or ``result``.
    bucket_key : str | None
        DRC bucket key when the impact is bucket-scoped.
    category : str | None
        DRC category or risk-class label when known.
    baseline_amount : float
        Baseline amount at this grain.
    candidate_amount : float
        Candidate amount at this grain.
    delta : float
        ``candidate_amount - baseline_amount``.
    method : DrcImpactMethod | str
        Finite-difference, residual, or unsupported impact classification.
    reason : str
        Human-readable explanation of the comparison branch.
    citations : tuple[str, ...]
        Regulatory citations retained from the compared result graph nodes.
    baseline_input_hash : str
        Baseline run input hash.
    candidate_input_hash : str
        Candidate run input hash.
    baseline_profile_hash : str
        Baseline profile hash.
    candidate_profile_hash : str
        Candidate profile hash.
    reconciliation_status : ReconciliationStatus
        Whether the record is an allocated finite-difference item or an explicit
        residual/unsupported item needed for reconciliation.
    """

    impact_id: str
    source_id: str
    source_level: str
    bucket_key: str | None
    category: str | None
    baseline_amount: float
    candidate_amount: float
    delta: float
    method: DrcImpactMethod | str
    reason: str
    citations: tuple[str, ...]
    baseline_input_hash: str
    candidate_input_hash: str
    baseline_profile_hash: str = ""
    candidate_profile_hash: str = ""
    reconciliation_status: ReconciliationStatus | str = ReconciliationStatus.RECONCILED

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", DrcImpactMethod(self.method))
        object.__setattr__(
            self,
            "reconciliation_status",
            ReconciliationStatus(self.reconciliation_status),
        )
        object.__setattr__(self, "citations", tuple(self.citations))
        expected = self.candidate_amount - self.baseline_amount
        tolerance = 1e-12 * max(
            abs(self.baseline_amount),
            abs(self.candidate_amount),
            1.0,
        )
        if abs(self.delta - expected) > tolerance:
            raise ValueError(
                f"delta {self.delta!r} does not equal candidate_amount - baseline_amount "
                f"({expected!r}) within tolerance {tolerance:.2e}"
            )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable mapping of impact record fields.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through the shared serializer.
        """

        return dataclass_as_dict(self)


@dataclass(frozen=True)
class DrcImpactAnalysis:
    """DRC impact analysis for two completed result graphs.

    Parameters
    ----------
    run_impact : CapitalImpact
        Package-neutral run-level impact record.
    records : tuple[DrcImpactRecord, ...]
        Package-local records explaining the run-level delta.
    residual : float
        Unexplained delta after summing records.
    reconciliation_status : ReconciliationStatus
        Aggregate reconciliation status for the analysis.
    """

    run_impact: CapitalImpact
    records: tuple[DrcImpactRecord, ...]
    residual: float
    reconciliation_status: ReconciliationStatus | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(
            self,
            "reconciliation_status",
            ReconciliationStatus(self.reconciliation_status),
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable mapping of impact analysis fields.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through the shared serializer.
        """

        return dataclass_as_dict(self)


def calculate_drc_impact(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    tolerance: float = _TOLERANCE,
) -> DrcImpactAnalysis:
    """Compare two completed DRC results without recalculating capital.

    Parameters
    ----------
    baseline : DrcCapitalResult
        Baseline DRC capital result.
    candidate : DrcCapitalResult
        Candidate DRC capital result.
    tolerance : float, optional
        Absolute reconciliation tolerance for record sums versus run delta.

    Returns
    -------
    DrcImpactAnalysis
        Run-level impact plus deterministic DRC impact records.

    Raises
    ------
    DrcInputError
        If either result has non-finite capital or the generated records do not
        reconcile to the run-level delta.
    """

    _validate_result(baseline, "baseline")
    _validate_result(candidate, "candidate")
    run_impact = CapitalImpact(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        component=_COMPONENT,
        baseline_total=baseline.total_drc,
        candidate_total=candidate.total_drc,
        delta=candidate.total_drc - baseline.total_drc,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
        notes=_run_notes(baseline, candidate),
    )

    if baseline.profile_id != candidate.profile_id:
        records = (
            _result_record(
                baseline,
                candidate,
                method=DrcImpactMethod.UNSUPPORTED,
                reason=(
                    "profile changed from "
                    f"{baseline.profile_id} to {candidate.profile_id}; "
                    "granular DRC impact is unsupported"
                ),
            ),
        )
    else:
        records = _bucket_records(baseline, candidate, tolerance=tolerance)

    record_delta = math.fsum(record.delta for record in records)
    residual = run_impact.delta - record_delta
    if abs(residual) > tolerance:
        records = (*records, _residual_record(baseline, candidate, residual))
        record_delta = math.fsum(record.delta for record in records)
        residual = run_impact.delta - record_delta

    if abs(residual) > tolerance:
        raise DrcInputError("DRC impact records do not reconcile to total capital delta")

    return DrcImpactAnalysis(
        run_impact=run_impact,
        records=records,
        residual=residual,
        reconciliation_status=_analysis_status(records),
    )


def validate_drc_impact_reconciliation(
    analysis: DrcImpactAnalysis,
    *,
    tolerance: float = _TOLERANCE,
) -> None:
    """Validate that DRC impact records reconcile to the run-level delta.

    Parameters
    ----------
    analysis : DrcImpactAnalysis
        Analysis to validate.
    tolerance : float, optional
        Absolute reconciliation tolerance.
    """

    record_delta = math.fsum(record.delta for record in analysis.records)
    if abs(record_delta - analysis.run_impact.delta) > tolerance:
        raise DrcInputError("DRC impact records do not reconcile to total capital delta")


def _bucket_records(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    tolerance: float,
) -> tuple[DrcImpactRecord, ...]:
    baseline_categories = _category_by_risk_class(baseline)
    candidate_categories = _category_by_risk_class(candidate)
    baseline_buckets = _bucket_by_key(baseline_categories)
    candidate_buckets = _bucket_by_key(candidate_categories)
    baseline_locations = _bucket_location_by_id(baseline_categories)
    candidate_locations = _bucket_location_by_id(candidate_categories)
    records: list[DrcImpactRecord] = []

    for key in sorted(set(baseline_buckets) | set(candidate_buckets)):
        baseline_bucket = baseline_buckets.get(key)
        candidate_bucket = candidate_buckets.get(key)
        baseline_category = baseline_categories.get(key[0])
        candidate_category = candidate_categories.get(key[0])
        baseline_amount = 0.0 if baseline_bucket is None else baseline_bucket.capital
        candidate_amount = 0.0 if candidate_bucket is None else candidate_bucket.capital
        if abs(candidate_amount - baseline_amount) <= tolerance:
            continue
        method, reason = _bucket_method_reason(
            key=key,
            baseline_bucket=baseline_bucket,
            candidate_bucket=candidate_bucket,
            baseline_category=baseline_category,
            candidate_category=candidate_category,
            baseline_locations=baseline_locations,
            candidate_locations=candidate_locations,
        )
        records.append(
            _record(
                baseline,
                candidate,
                source_id=_source_id(baseline_bucket, candidate_bucket, key),
                source_level="bucket",
                bucket_key=key[1],
                category=key[0],
                baseline_amount=baseline_amount,
                candidate_amount=candidate_amount,
                method=method,
                reason=reason,
                citations=_citations(baseline_bucket, candidate_bucket),
            )
        )
    return tuple(records)


def _bucket_method_reason(
    *,
    key: tuple[str, str],
    baseline_bucket: BucketDrc | None,
    candidate_bucket: BucketDrc | None,
    baseline_category: CategoryDrc | None,
    candidate_category: CategoryDrc | None,
    baseline_locations: Mapping[str, tuple[str, str]],
    candidate_locations: Mapping[str, tuple[str, str]],
) -> tuple[DrcImpactMethod, str]:
    baseline_unsupported = _has_unsupported_branch(baseline_category, baseline_bucket)
    candidate_unsupported = _has_unsupported_branch(candidate_category, candidate_bucket)
    if baseline_unsupported or candidate_unsupported:
        return (
            DrcImpactMethod.UNSUPPORTED,
            "floor or unsupported branch metadata makes granular DRC impact unsupported",
        )
    if baseline_bucket is None or candidate_bucket is None:
        bucket_id = _moved_bucket_id(baseline_locations, candidate_locations)
        if bucket_id is not None:
            before = baseline_locations.get(bucket_id)
            after = candidate_locations.get(bucket_id)
            return (
                DrcImpactMethod.UNSUPPORTED,
                f"bucket/category move for bucket {bucket_id}: {before} to {after}",
            )
        return (
            DrcImpactMethod.UNSUPPORTED,
            f"bucket {key[1]} was added or removed; exact impact allocation is unsupported",
        )
    return (
        DrcImpactMethod.FINITE_DIFFERENCE,
        "finite-difference impact over stable DRC bucket branch",
    )


def _record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    source_id: str,
    source_level: str,
    bucket_key: str | None,
    category: str | None,
    baseline_amount: float,
    candidate_amount: float,
    method: DrcImpactMethod,
    reason: str,
    citations: tuple[str, ...] = (),
) -> DrcImpactRecord:
    return DrcImpactRecord(
        impact_id=(
            f"drc-impact-{method.value.lower()}-"
            f"{_slug(source_level)}-{_slug(source_id)}"
        ),
        source_id=source_id,
        source_level=source_level,
        bucket_key=bucket_key,
        category=category,
        baseline_amount=baseline_amount,
        candidate_amount=candidate_amount,
        delta=candidate_amount - baseline_amount,
        method=method,
        reason=reason,
        citations=citations,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
        reconciliation_status=(
            ReconciliationStatus.RECONCILED
            if method is DrcImpactMethod.FINITE_DIFFERENCE
            else ReconciliationStatus.PARTIAL_RESIDUAL
        ),
    )


def _result_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    method: DrcImpactMethod,
    reason: str,
) -> DrcImpactRecord:
    return _record(
        baseline,
        candidate,
        source_id=f"{baseline.result_id}->{candidate.result_id}",
        source_level="result",
        bucket_key=None,
        category=None,
        baseline_amount=baseline.total_drc,
        candidate_amount=candidate.total_drc,
        method=method,
        reason=reason,
        citations=_sorted_unique((*baseline.citations, *candidate.citations)),
    )


def _residual_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    residual: float,
) -> DrcImpactRecord:
    return DrcImpactRecord(
        impact_id=(
            f"drc-impact-residual-{_slug(baseline.result_id)}-"
            f"{_slug(candidate.result_id)}"
        ),
        source_id=f"{baseline.result_id}->{candidate.result_id}",
        source_level="result",
        bucket_key=None,
        category=None,
        baseline_amount=0.0,
        candidate_amount=residual,
        delta=residual,
        method=DrcImpactMethod.RESIDUAL,
        reason="residual reconciles DRC impact records to run-level capital delta",
        citations=_sorted_unique((*baseline.citations, *candidate.citations)),
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )


def _category_by_risk_class(result: DrcCapitalResult) -> dict[str, CategoryDrc]:
    return {str(category.risk_class): category for category in result.categories}


def _bucket_by_key(
    categories: Mapping[str, CategoryDrc],
) -> dict[tuple[str, str], BucketDrc]:
    buckets: dict[tuple[str, str], BucketDrc] = {}
    for risk_class, category in categories.items():
        for bucket in category.bucket_results:
            buckets[(risk_class, bucket.bucket_key)] = bucket
    return buckets


def _bucket_location_by_id(
    categories: Mapping[str, CategoryDrc],
) -> dict[str, tuple[str, str]]:
    locations: dict[str, tuple[str, str]] = {}
    for risk_class, category in categories.items():
        for bucket in category.bucket_results:
            locations[bucket.bucket_id] = (risk_class, bucket.bucket_key)
    return locations


def _moved_bucket_id(
    baseline_locations: Mapping[str, tuple[str, str]],
    candidate_locations: Mapping[str, tuple[str, str]],
) -> str | None:
    for bucket_id in sorted(set(baseline_locations) & set(candidate_locations)):
        if baseline_locations[bucket_id] != candidate_locations[bucket_id]:
            return bucket_id
    return None


def _has_unsupported_branch(
    category: CategoryDrc | None,
    bucket: BucketDrc | None,
) -> bool:
    if category is not None and category.unsupported_features:
        return True
    nodes: tuple[object, ...] = tuple(
        item
        for item in (category, bucket, None if bucket is None else bucket.hbr)
        if item is not None
    )
    for node in nodes:
        if getattr(node, "floor_applied", False):
            return True
        for branch in getattr(node, "branch_metadata", ()):
            if BranchType(branch.branch_type) in {
                BranchType.FLOOR,
                BranchType.UNSUPPORTED_FEATURE,
                BranchType.ZERO_DENOMINATOR,
            }:
                return True
    return False


def _source_id(
    baseline_bucket: BucketDrc | None,
    candidate_bucket: BucketDrc | None,
    key: tuple[str, str],
) -> str:
    if candidate_bucket is not None:
        return candidate_bucket.bucket_id
    if baseline_bucket is not None:
        return baseline_bucket.bucket_id
    return ":".join(key)


def _citations(
    baseline_bucket: BucketDrc | None,
    candidate_bucket: BucketDrc | None,
) -> tuple[str, ...]:
    citations: list[str] = []
    for bucket in (baseline_bucket, candidate_bucket):
        if bucket is not None:
            citations.extend(bucket.citations)
            citations.extend(
                citation for branch in bucket.branch_metadata for citation in branch.citations
            )
    return _sorted_unique(citations)


def _run_notes(baseline: DrcCapitalResult, candidate: DrcCapitalResult) -> tuple[str, ...]:
    notes: list[str] = []
    if baseline.profile_id != candidate.profile_id:
        notes.append("profile change makes granular DRC impact unsupported")
    if baseline.base_currency != candidate.base_currency:
        notes.append("base currency changed between baseline and candidate")
    return tuple(notes)


def _analysis_status(records: tuple[DrcImpactRecord, ...]) -> ReconciliationStatus:
    if not records:
        return ReconciliationStatus.RECONCILED
    if any(record.method is DrcImpactMethod.UNSUPPORTED for record in records):
        return ReconciliationStatus.PARTIAL_RESIDUAL
    if any(record.method is DrcImpactMethod.RESIDUAL for record in records):
        return ReconciliationStatus.PARTIAL_RESIDUAL
    return ReconciliationStatus.RECONCILED


def _validate_result(result: DrcCapitalResult, label: str) -> None:
    if not math.isfinite(result.total_drc):
        raise DrcInputError(f"{label} total_drc must be finite")


def _sorted_unique(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value is not None and str(value) != ""}))


__all__ = [
    "DrcImpactAnalysis",
    "DrcImpactMethod",
    "DrcImpactRecord",
    "calculate_drc_impact",
    "validate_drc_impact_reconciliation",
]
