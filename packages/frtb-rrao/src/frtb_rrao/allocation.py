"""
Deterministic additive RRAO allocation reports.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for allocation.py, Basel MAR23.8,
    U.S. NPR 2.0 proposed section __.211(c), and EU Article 325u(3).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date

from frtb_rrao.audit import validate_rrao_result_reconciliation
from frtb_rrao.data_models import (
    RraoAllocationBucket,
    RraoAllocationDimension,
    RraoAllocationReport,
    RraoCapitalLine,
    RraoCapitalResult,
)
from frtb_rrao.validation import RraoInputError

SUPPORTED_RRAO_ALLOCATION_DIMENSIONS = (
    RraoAllocationDimension.LINE,
    RraoAllocationDimension.DESK,
    RraoAllocationDimension.LEGAL_ENTITY,
    RraoAllocationDimension.EVIDENCE_TYPE,
)

_ALLOCATION_METHOD = "additive_line_add_on"
_RECONCILIATION_TOLERANCE = 1e-9
_DIMENSION_ALIASES = {
    "line": RraoAllocationDimension.LINE,
    "desk": RraoAllocationDimension.DESK,
    "desk_id": RraoAllocationDimension.DESK,
    "legal_entity": RraoAllocationDimension.LEGAL_ENTITY,
    "legal-entity": RraoAllocationDimension.LEGAL_ENTITY,
    "evidence_type": RraoAllocationDimension.EVIDENCE_TYPE,
    "evidence-type": RraoAllocationDimension.EVIDENCE_TYPE,
}


def build_rrao_allocation_report(
    result: RraoCapitalResult,
    dimension: RraoAllocationDimension | str,
) -> RraoAllocationReport:
    """Build a deterministic additive allocation report for one dimension."""

    if not isinstance(result, RraoCapitalResult):
        raise RraoInputError("result must be RraoCapitalResult", field="result")

    resolved_dimension = resolve_rrao_allocation_dimension(dimension)
    validate_rrao_result_reconciliation(result)
    lines = result.lines + result.excluded_lines
    if resolved_dimension is RraoAllocationDimension.LINE:
        buckets = tuple(
            _bucket_for_lines(resolved_dimension, line.position_id, (line,)) for line in lines
        )
    else:
        buckets = _grouped_buckets(lines, resolved_dimension)

    report = RraoAllocationReport(
        run_id=result.run_id,
        calculation_date=result.calculation_date,
        base_currency=result.base_currency,
        profile_id=result.profile_id,
        input_hash=result.input_hash,
        dimension=resolved_dimension,
        allocation_method=_ALLOCATION_METHOD,
        total_rrao=result.total_rrao,
        allocated_rrao=sum(bucket.add_on for bucket in buckets),
        buckets=buckets,
    )
    validate_rrao_allocation_report(report)
    return report


def build_rrao_allocation_reports(
    result: RraoCapitalResult,
    dimensions: Iterable[RraoAllocationDimension | str] = SUPPORTED_RRAO_ALLOCATION_DIMENSIONS,
) -> tuple[RraoAllocationReport, ...]:
    """Build deterministic allocation reports for supported dimensions."""

    return tuple(build_rrao_allocation_report(result, dimension) for dimension in dimensions)


def resolve_rrao_allocation_dimension(
    dimension: RraoAllocationDimension | str,
) -> RraoAllocationDimension:
    """Return a supported RRAO allocation dimension or fail closed."""

    if isinstance(dimension, RraoAllocationDimension):
        return dimension
    if not isinstance(dimension, str) or not dimension.strip():
        raise RraoInputError("allocation dimension must be non-empty text", field="dimension")

    key = dimension.strip().lower()
    if key in _DIMENSION_ALIASES:
        return _DIMENSION_ALIASES[key]

    supported = ", ".join(item.value for item in SUPPORTED_RRAO_ALLOCATION_DIMENSIONS)
    raise RraoInputError(
        f"unsupported RRAO allocation dimension {dimension!r}; supported dimensions: {supported}",
        field="dimension",
    )


def validate_rrao_allocation_report(report: RraoAllocationReport) -> None:
    """Raise when an allocation report does not reconcile to its bucket records."""

    if not isinstance(report, RraoAllocationReport):
        raise RraoInputError("report must be RraoAllocationReport", field="report")
    if report.dimension not in SUPPORTED_RRAO_ALLOCATION_DIMENSIONS:
        raise RraoInputError("unsupported RRAO allocation dimension", field="dimension")
    if not isinstance(report.calculation_date, date):
        raise RraoInputError("calculation date must be a date", field="calculation_date")
    if report.allocation_method != _ALLOCATION_METHOD:
        raise RraoInputError("unsupported RRAO allocation method", field="allocation_method")

    bucket_total = sum(bucket.add_on for bucket in report.buckets)
    if not math.isclose(
        report.allocated_rrao,
        bucket_total,
        rel_tol=0.0,
        abs_tol=_RECONCILIATION_TOLERANCE,
    ):
        raise RraoInputError("allocated RRAO does not reconcile to buckets", field="buckets")
    if not math.isclose(
        report.total_rrao,
        report.allocated_rrao,
        rel_tol=0.0,
        abs_tol=_RECONCILIATION_TOLERANCE,
    ):
        raise RraoInputError("allocation does not reconcile to total RRAO", field="total_rrao")

    seen_bucket_keys: set[str] = set()
    for bucket in report.buckets:
        _validate_bucket(report.dimension, bucket, seen_bucket_keys)


def serialize_rrao_allocation_report(report: RraoAllocationReport) -> dict[str, object]:
    """Return a JSON-serialisable deterministic allocation report payload."""

    validate_rrao_allocation_report(report)
    return {
        "run_id": report.run_id,
        "calculation_date": report.calculation_date.isoformat(),
        "base_currency": report.base_currency,
        "profile_id": report.profile_id,
        "input_hash": report.input_hash,
        "dimension": report.dimension.value,
        "allocation_method": report.allocation_method,
        "total_rrao": report.total_rrao,
        "allocated_rrao": report.allocated_rrao,
        "buckets": [_normalise_bucket(bucket) for bucket in report.buckets],
    }


def _grouped_buckets(
    lines: tuple[RraoCapitalLine, ...],
    dimension: RraoAllocationDimension,
) -> tuple[RraoAllocationBucket, ...]:
    grouped: dict[str, list[RraoCapitalLine]] = {}
    for line in lines:
        grouped.setdefault(_bucket_key(line, dimension), []).append(line)
    return tuple(
        _bucket_for_lines(dimension, bucket_key, tuple(grouped[bucket_key]))
        for bucket_key in sorted(grouped)
    )


def _bucket_for_lines(
    dimension: RraoAllocationDimension,
    bucket_key: str,
    lines: tuple[RraoCapitalLine, ...],
) -> RraoAllocationBucket:
    included_position_ids = tuple(line.position_id for line in lines if not line.is_excluded)
    excluded_position_ids = tuple(line.position_id for line in lines if line.is_excluded)
    return RraoAllocationBucket(
        dimension=dimension,
        bucket_key=bucket_key,
        gross_effective_notional=sum(line.gross_effective_notional for line in lines),
        add_on=sum(line.add_on for line in lines),
        position_ids=tuple(line.position_id for line in lines),
        included_position_ids=included_position_ids,
        excluded_position_ids=excluded_position_ids,
        line_count=len(lines),
        excluded_line_count=len(excluded_position_ids),
    )


def _bucket_key(line: RraoCapitalLine, dimension: RraoAllocationDimension) -> str:
    if dimension is RraoAllocationDimension.DESK:
        return line.desk_id
    if dimension is RraoAllocationDimension.LEGAL_ENTITY:
        return line.legal_entity
    if dimension is RraoAllocationDimension.EVIDENCE_TYPE:
        return line.evidence_type.value
    if dimension is RraoAllocationDimension.LINE:
        return line.position_id
    raise RraoInputError("unsupported RRAO allocation dimension", field="dimension")


def _validate_bucket(
    dimension: RraoAllocationDimension,
    bucket: RraoAllocationBucket,
    seen_bucket_keys: set[str],
) -> None:
    if bucket.dimension is not dimension:
        raise RraoInputError("allocation bucket dimension mismatch", field="buckets")
    if not bucket.bucket_key.strip():
        raise RraoInputError("allocation bucket key is required", field="buckets")
    if bucket.bucket_key in seen_bucket_keys:
        raise RraoInputError("duplicate allocation bucket key", field="buckets")
    seen_bucket_keys.add(bucket.bucket_key)
    if bucket.line_count != len(bucket.position_ids):
        raise RraoInputError("allocation bucket line count mismatch", field="buckets")
    if bucket.excluded_line_count != len(bucket.excluded_position_ids):
        raise RraoInputError("allocation bucket excluded count mismatch", field="buckets")


def _normalise_bucket(bucket: RraoAllocationBucket) -> dict[str, object]:
    return {
        "dimension": bucket.dimension.value,
        "bucket_key": bucket.bucket_key,
        "gross_effective_notional": bucket.gross_effective_notional,
        "add_on": bucket.add_on,
        "position_ids": list(bucket.position_ids),
        "included_position_ids": list(bucket.included_position_ids),
        "excluded_position_ids": list(bucket.excluded_position_ids),
        "line_count": bucket.line_count,
        "excluded_line_count": bucket.excluded_line_count,
    }


__all__ = [
    "SUPPORTED_RRAO_ALLOCATION_DIMENSIONS",
    "build_rrao_allocation_report",
    "build_rrao_allocation_reports",
    "resolve_rrao_allocation_dimension",
    "serialize_rrao_allocation_report",
    "validate_rrao_allocation_report",
]
