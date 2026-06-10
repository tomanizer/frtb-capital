"""Build branch-aware DRC impact records from two capital results."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from frtb_drc._impact_models import DrcImpactRecord
from frtb_drc._impact_record_factories import (
    finite_difference_record,
    has_unsupported_branch,
    unsupported_record,
)
from frtb_drc.data_models import (
    BucketDrc,
    CategoryDrc,
    DrcCapitalResult,
    DrcPosition,
    DrcRiskClass,
)


def impact_records(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
) -> tuple[DrcImpactRecord, ...]:
    """Build DRC-specific impact records for a compatible result pair.

    Parameters
    ----------
    baseline : DrcCapitalResult
        Completed baseline DRC result graph.
    candidate : DrcCapitalResult
        Completed candidate DRC result graph.

    Returns
    -------
    tuple[DrcImpactRecord, ...]
        Deterministically ordered DRC impact records.
    """

    records: list[DrcImpactRecord] = []
    records.extend(_profile_change_records(baseline, candidate))
    records.extend(_position_move_records(baseline, candidate))

    baseline_categories = {category.category_id: category for category in baseline.categories}
    candidate_categories = {category.category_id: category for category in candidate.categories}
    for category_id in sorted(set(baseline_categories) | set(candidate_categories)):
        baseline_category = baseline_categories.get(category_id)
        candidate_category = candidate_categories.get(category_id)
        if baseline_category is None or candidate_category is None:
            records.append(_category_unsupported_record(baseline, candidate, category_id))
            continue
        records.extend(
            _category_records(baseline, candidate, baseline_category, candidate_category)
        )
    return tuple(records)


def _category_records(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    baseline_category: CategoryDrc,
    candidate_category: CategoryDrc,
) -> tuple[DrcImpactRecord, ...]:
    risk_class = str(DrcRiskClass(baseline_category.risk_class))
    if DrcRiskClass(baseline_category.risk_class) != DrcRiskClass(candidate_category.risk_class):
        return (
            unsupported_record(
                baseline,
                candidate,
                source_id=baseline_category.category_id,
                source_level="category",
                baseline_capital=baseline_category.capital,
                candidate_capital=candidate_category.capital,
                baseline_category=risk_class,
                candidate_category=str(DrcRiskClass(candidate_category.risk_class)),
                reason="category risk class changed; exact branch impact is unsupported",
                branch_metadata=(
                    *baseline_category.branch_metadata,
                    *candidate_category.branch_metadata,
                ),
                metadata={"impact_class": "category_move"},
            ),
        )
    if has_unsupported_branch(baseline_category) or has_unsupported_branch(candidate_category):
        return (
            unsupported_record(
                baseline,
                candidate,
                source_id=baseline_category.category_id,
                source_level="category",
                baseline_capital=baseline_category.capital,
                candidate_capital=candidate_category.capital,
                baseline_category=risk_class,
                candidate_category=risk_class,
                reason="category branch metadata prevents exact finite-difference decomposition",
                branch_metadata=(
                    *baseline_category.branch_metadata,
                    *candidate_category.branch_metadata,
                ),
                metadata={"impact_class": "unsupported_category_branch"},
            ),
        )

    baseline_buckets = {bucket.bucket_id: bucket for bucket in baseline_category.bucket_results}
    candidate_buckets = {bucket.bucket_id: bucket for bucket in candidate_category.bucket_results}
    return tuple(
        _bucket_record(
            baseline,
            candidate,
            category=risk_class,
            bucket_id=bucket_id,
            baseline_bucket=baseline_buckets.get(bucket_id),
            candidate_bucket=candidate_buckets.get(bucket_id),
        )
        for bucket_id in sorted(set(baseline_buckets) | set(candidate_buckets))
    )


def _bucket_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    category: str,
    bucket_id: str,
    baseline_bucket: BucketDrc | None,
    candidate_bucket: BucketDrc | None,
) -> DrcImpactRecord:
    baseline_capital = None if baseline_bucket is None else baseline_bucket.capital
    candidate_capital = None if candidate_bucket is None else candidate_bucket.capital
    branch_metadata = (
        *(baseline_bucket.branch_metadata if baseline_bucket is not None else ()),
        *(candidate_bucket.branch_metadata if candidate_bucket is not None else ()),
        *(baseline_bucket.hbr.branch_metadata if baseline_bucket is not None else ()),
        *(candidate_bucket.hbr.branch_metadata if candidate_bucket is not None else ()),
    )
    if baseline_bucket is None or candidate_bucket is None:
        return unsupported_record(
            baseline,
            candidate,
            source_id=bucket_id,
            source_level="bucket",
            baseline_capital=baseline_capital,
            candidate_capital=candidate_capital,
            baseline_category=category if baseline_bucket is not None else None,
            candidate_category=category if candidate_bucket is not None else None,
            baseline_bucket_key=None if baseline_bucket is None else baseline_bucket.bucket_key,
            candidate_bucket_key=None if candidate_bucket is None else candidate_bucket.bucket_key,
            reason="bucket appeared or disappeared; exact branch impact is unsupported",
            branch_metadata=branch_metadata,
            metadata={"impact_class": "bucket_move"},
        )
    if has_unsupported_branch(baseline_bucket, baseline_bucket.hbr) or has_unsupported_branch(
        candidate_bucket, candidate_bucket.hbr
    ):
        return unsupported_record(
            baseline,
            candidate,
            source_id=bucket_id,
            source_level="bucket",
            baseline_capital=baseline_capital,
            candidate_capital=candidate_capital,
            baseline_category=category,
            candidate_category=category,
            baseline_bucket_key=baseline_bucket.bucket_key,
            candidate_bucket_key=candidate_bucket.bucket_key,
            reason="bucket floor or HBR branch prevents exact finite-difference decomposition",
            branch_metadata=branch_metadata,
            metadata={"impact_class": "unsupported_bucket_branch"},
        )
    return finite_difference_record(
        baseline,
        candidate,
        source_id=bucket_id,
        source_level="bucket",
        baseline_capital=baseline_capital,
        candidate_capital=candidate_capital,
        baseline_category=category,
        candidate_category=category,
        baseline_bucket_key=baseline_bucket.bucket_key,
        candidate_bucket_key=candidate_bucket.bucket_key,
        reason="finite-difference impact over stable DRC bucket branch",
        branch_metadata=branch_metadata,
    )


def _profile_change_records(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
) -> tuple[DrcImpactRecord, ...]:
    if (
        baseline.profile_id == candidate.profile_id
        and baseline.profile_hash == candidate.profile_hash
    ):
        return ()
    return (
        unsupported_record(
            baseline,
            candidate,
            source_id="profile",
            source_level="profile",
            baseline_capital=baseline.total_drc,
            candidate_capital=candidate.total_drc,
            reason="profile identity or profile hash changed; exact branch impact is unsupported",
            branch_metadata=(*baseline.branch_metadata, *candidate.branch_metadata),
            metadata={
                "baseline_profile_id": baseline.profile_id,
                "candidate_profile_id": candidate.profile_id,
                "impact_class": "profile_change",
            },
        ),
    )


def _position_move_records(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
) -> tuple[DrcImpactRecord, ...]:
    baseline_positions = _position_locations(baseline.input_positions)
    candidate_positions = _position_locations(candidate.input_positions)
    return tuple(
        unsupported_record(
            baseline,
            candidate,
            source_id=position_id,
            source_level="position",
            baseline_capital=None,
            candidate_capital=None,
            baseline_category=baseline_positions[position_id][0],
            candidate_category=candidate_positions[position_id][0],
            baseline_bucket_key=baseline_positions[position_id][1],
            candidate_bucket_key=candidate_positions[position_id][1],
            reason="position moved bucket or category; exact branch impact is unsupported",
            metadata={
                "baseline_bucket_key": baseline_positions[position_id][1],
                "candidate_bucket_key": candidate_positions[position_id][1],
                "impact_class": "position_move",
            },
        )
        for position_id in sorted(set(baseline_positions) & set(candidate_positions))
        if baseline_positions[position_id] != candidate_positions[position_id]
    )


def _position_locations(
    positions: tuple[DrcPosition, ...],
) -> Mapping[str, tuple[str, str | None]]:
    return MappingProxyType(
        {
            position.position_id: (
                str(DrcRiskClass(position.risk_class)),
                position.bucket_key,
            )
            for position in positions
        }
    )


def _category_unsupported_record(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    category_id: str,
) -> DrcImpactRecord:
    baseline_category = next(
        (item for item in baseline.categories if item.category_id == category_id),
        None,
    )
    candidate_category = next(
        (item for item in candidate.categories if item.category_id == category_id),
        None,
    )
    baseline_risk_class = (
        None if baseline_category is None else str(DrcRiskClass(baseline_category.risk_class))
    )
    candidate_risk_class = (
        None if candidate_category is None else str(DrcRiskClass(candidate_category.risk_class))
    )
    return unsupported_record(
        baseline,
        candidate,
        source_id=category_id,
        source_level="category",
        baseline_capital=None if baseline_category is None else baseline_category.capital,
        candidate_capital=None if candidate_category is None else candidate_category.capital,
        baseline_category=baseline_risk_class,
        candidate_category=candidate_risk_class,
        reason="category appeared or disappeared; exact branch impact is unsupported",
        branch_metadata=(
            *(baseline_category.branch_metadata if baseline_category is not None else ()),
            *(candidate_category.branch_metadata if candidate_category is not None else ()),
        ),
        metadata={"impact_class": "category_move"},
    )
