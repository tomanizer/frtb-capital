"""Factory helpers for DRC impact records."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from frtb_common.attribution import ReconciliationStatus

from frtb_drc._identifiers import slug_path as _slug
from frtb_drc._impact_models import DrcImpactMethod, DrcImpactRecord
from frtb_drc.data_models import BranchMetadata, BranchType, DrcCapitalResult


def finite_difference_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    source_id: str,
    source_level: str,
    baseline_capital: float | None,
    candidate_capital: float | None,
    reason: str,
    baseline_category: str | None = None,
    candidate_category: str | None = None,
    baseline_bucket_key: str | None = None,
    candidate_bucket_key: str | None = None,
    branch_metadata: Iterable[BranchMetadata] = (),
) -> DrcImpactRecord:
    """Create a reconciled finite-difference impact record."""

    baseline_amount = 0.0 if baseline_capital is None else baseline_capital
    candidate_amount = 0.0 if candidate_capital is None else candidate_capital
    return DrcImpactRecord(
        impact_id=f"impact-{source_level}-{_slug(source_id)}",
        source_id=source_id,
        source_level=source_level,
        baseline_capital=baseline_capital,
        candidate_capital=candidate_capital,
        delta=candidate_amount - baseline_amount,
        method=DrcImpactMethod.FINITE_DIFFERENCE,
        reconciliation_status=ReconciliationStatus.RECONCILED,
        reason=reason,
        baseline_category=baseline_category,
        candidate_category=candidate_category,
        baseline_bucket_key=baseline_bucket_key,
        candidate_bucket_key=candidate_bucket_key,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
        branch_metadata=tuple(branch_metadata),
    )


def unsupported_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    source_id: str,
    source_level: str,
    baseline_capital: float | None,
    candidate_capital: float | None,
    reason: str,
    baseline_category: str | None = None,
    candidate_category: str | None = None,
    baseline_bucket_key: str | None = None,
    candidate_bucket_key: str | None = None,
    branch_metadata: Iterable[BranchMetadata] = (),
    metadata: Mapping[str, object] | None = None,
) -> DrcImpactRecord:
    """Create an unsupported impact record with preserved result metadata."""

    return DrcImpactRecord(
        impact_id=f"impact-unsupported-{source_level}-{_slug(source_id)}",
        source_id=source_id,
        source_level=source_level,
        baseline_capital=baseline_capital,
        candidate_capital=candidate_capital,
        delta=None,
        method=DrcImpactMethod.UNSUPPORTED,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
        reason=reason,
        baseline_category=baseline_category,
        candidate_category=candidate_category,
        baseline_bucket_key=baseline_bucket_key,
        candidate_bucket_key=candidate_bucket_key,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
        branch_metadata=tuple(branch_metadata),
        metadata={} if metadata is None else metadata,
    )


def residual_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    residual: float,
    reason: str,
) -> DrcImpactRecord:
    """Create the total residual record for unexplained capital delta."""

    return DrcImpactRecord(
        impact_id="impact-residual-total",
        source_id="total",
        source_level="residual",
        baseline_capital=None,
        candidate_capital=None,
        delta=residual,
        method=DrcImpactMethod.RESIDUAL,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
        reason=reason,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
    )


def record_delta_sum(records: tuple[DrcImpactRecord, ...]) -> float:
    """Sum numeric deltas, ignoring unsupported records with no delta."""

    return math.fsum(record.delta or 0.0 for record in records)


def reconciled_delta(records: tuple[DrcImpactRecord, ...]) -> float:
    """Sum deltas from finite-difference records only."""

    return math.fsum(
        record.delta or 0.0
        for record in records
        if DrcImpactMethod(record.method) == DrcImpactMethod.FINITE_DIFFERENCE
    )


def has_unsupported_branch(*records: object) -> bool:
    """Return true when any record carries a branch unsupported for impact."""

    unsupported = {
        BranchType.FLOOR,
        BranchType.ZERO_DENOMINATOR,
        BranchType.UNSUPPORTED_FEATURE,
        BranchType.OFFSET_REJECTED,
    }
    for record in records:
        if getattr(record, "floor_applied", False):
            return True
        branches = getattr(record, "branch_metadata", ())
        if any(BranchType(branch.branch_type) in unsupported for branch in branches):
            return True
    return False
