"""DRC attribution over an already calculated capital result."""

from __future__ import annotations

import math
from collections.abc import Mapping

from frtb_drc.data_models import (
    AttributionMethod,
    BranchType,
    BucketDrc,
    CategoryDrc,
    DefaultDirection,
    DrcCapitalContribution,
    DrcCapitalResult,
    DrcRiskClass,
    NetJtd,
)
from frtb_drc.validation import DrcInputError

_TOLERANCE = 1e-9


def calculate_drc_attribution(
    result: DrcCapitalResult,
    *,
    risk_weights_by_position: Mapping[str, float],
    tolerance: float = _TOLERANCE,
) -> tuple[DrcCapitalContribution, ...]:
    """Calculate deterministic DRC attribution records without changing capital."""

    net_by_id = {record.net_jtd_id: record for record in result.net_jtds}
    records: list[DrcCapitalContribution] = []
    for category in result.categories:
        records.extend(
            _category_contributions(
                category,
                net_by_id=net_by_id,
                risk_weights_by_position=risk_weights_by_position,
                tolerance=tolerance,
            )
        )
    validate_attribution_reconciliation(result, tuple(records), tolerance=tolerance)
    return tuple(records)


def validate_attribution_reconciliation(
    result: DrcCapitalResult,
    records: tuple[DrcCapitalContribution, ...] | None = None,
    *,
    tolerance: float = _TOLERANCE,
) -> None:
    """Validate that contributions plus residual records reconcile to total capital."""

    attribution_records = result.attribution_records if records is None else records
    total = math.fsum(
        (record.contribution or 0.0) + record.residual for record in attribution_records
    )
    if abs(total - result.total_drc) > tolerance:
        raise DrcInputError("DRC attribution records do not reconcile to total capital")


def _category_contributions(
    category: CategoryDrc,
    *,
    net_by_id: Mapping[str, NetJtd],
    risk_weights_by_position: Mapping[str, float],
    tolerance: float,
) -> tuple[DrcCapitalContribution, ...]:
    risk_class = DrcRiskClass(category.risk_class)
    if _has_branch(category, BranchType.FLOOR):
        return (
            _unsupported_record(
                source_id=category.category_id,
                source_level="category",
                bucket_key=None,
                category=risk_class,
                residual=category.capital,
                reason="category floor makes exact Euler attribution unsupported",
            ),
        )
    if not category.bucket_results:
        return (
            _residual_record(
                source_id=category.category_id,
                source_level="category",
                bucket_key=None,
                category=risk_class,
                residual=category.capital,
                reason="empty category capital residual",
            ),
        )

    bucket_factors = _bucket_category_factors(category)
    records: list[DrcCapitalContribution] = []
    category_contribution = 0.0
    category_weighted_short = sum(
        factor * item.weighted_short
        for item, factor in _bucket_factor_items(category, bucket_factors)
    )
    for bucket in category.bucket_results:
        weighted_short_factor = (
            category_weighted_short
            if risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
            else bucket.weighted_short
        )
        bucket_records = _bucket_contributions(
            bucket,
            category=risk_class,
            category_factor=bucket_factors[bucket.bucket_id],
            weighted_short_factor=weighted_short_factor,
            net_by_id=net_by_id,
            risk_weights_by_position=risk_weights_by_position,
        )
        records.extend(bucket_records)
        category_contribution += _record_sum(bucket_records)

    residual = category.capital - category_contribution
    if abs(residual) > tolerance:
        records.append(
            _residual_record(
                source_id=category.category_id,
                source_level="category",
                bucket_key=None,
                category=risk_class,
                residual=residual,
                reason=("category residual reconciles analytical contribution records to capital"),
            )
        )
    return tuple(records)


def _bucket_contributions(
    bucket: BucketDrc,
    *,
    category: DrcRiskClass,
    category_factor: float,
    weighted_short_factor: float,
    net_by_id: Mapping[str, NetJtd],
    risk_weights_by_position: Mapping[str, float],
) -> tuple[DrcCapitalContribution, ...]:
    if bucket.floor_applied or _has_branch(bucket, BranchType.FLOOR):
        return (
            _unsupported_record(
                source_id=bucket.bucket_id,
                source_level="bucket",
                bucket_key=bucket.bucket_key,
                category=category,
                residual=category_factor * bucket.capital,
                reason="bucket floor makes exact Euler attribution unsupported",
            ),
        )
    if bucket.hbr.denominator == 0.0 or _has_branch(bucket.hbr, BranchType.ZERO_DENOMINATOR):
        return (
            _unsupported_record(
                source_id=bucket.bucket_id,
                source_level="bucket",
                bucket_key=bucket.bucket_key,
                category=category,
                residual=category_factor * bucket.capital,
                reason="zero HBR denominator makes exact Euler attribution unsupported",
            ),
        )

    aggregate_long = bucket.hbr.aggregate_net_long
    aggregate_short = bucket.hbr.aggregate_net_short
    denominator_sq = bucket.hbr.denominator * bucket.hbr.denominator
    records: list[DrcCapitalContribution] = []
    for net_jtd_id in bucket.net_jtd_ids:
        net_jtd = net_by_id[net_jtd_id]
        risk_weight = _net_risk_weight(net_jtd, risk_weights_by_position)
        if risk_weight is None:
            return (
                _unsupported_record(
                    source_id=bucket.bucket_id,
                    source_level="bucket",
                    bucket_key=bucket.bucket_key,
                    category=category,
                    residual=category_factor * bucket.capital,
                    reason=(
                        "net JTD risk weight lineage is not unique; exact Euler "
                        "attribution is unsupported"
                    ),
                ),
            )
        if DefaultDirection(net_jtd.net_direction) == DefaultDirection.LONG:
            multiplier = category_factor * risk_weight
            multiplier -= weighted_short_factor * aggregate_short / denominator_sq
        else:
            multiplier = weighted_short_factor * aggregate_long / denominator_sq
            multiplier -= category_factor * bucket.hbr.ratio * risk_weight
        contribution = net_jtd.net_amount * multiplier
        records.append(
            DrcCapitalContribution(
                contribution_id=f"attr-{_slug(net_jtd.net_jtd_id)}",
                source_id=net_jtd.net_jtd_id,
                source_level="net_jtd",
                bucket_key=bucket.bucket_key,
                category=category,
                base_amount=net_jtd.net_amount,
                marginal_multiplier=multiplier,
                contribution=contribution,
                method=AttributionMethod.ANALYTICAL_EULER,
                reason="analytical Euler over stable DRC bucket/category branch",
            )
        )
    return tuple(records)


def _bucket_category_factors(category: CategoryDrc) -> dict[str, float]:
    if DrcRiskClass(category.risk_class) != DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return {bucket.bucket_id: 1.0 for bucket in category.bucket_results}
    return {
        bucket.bucket_id: 1.0 if bucket.capital >= 0.0 else 0.5
        for bucket in category.bucket_results
    }


def _bucket_factor_items(
    category: CategoryDrc,
    factors: Mapping[str, float],
) -> tuple[tuple[BucketDrc, float], ...]:
    return tuple((bucket, factors[bucket.bucket_id]) for bucket in category.bucket_results)


def _net_risk_weight(
    net_jtd: NetJtd,
    risk_weights_by_position: Mapping[str, float],
) -> float | None:
    weights: set[float] = set()
    for position_id in net_jtd.position_ids:
        risk_weight = risk_weights_by_position.get(position_id)
        if risk_weight is None or not math.isfinite(risk_weight) or risk_weight < 0.0:
            return None
        weights.add(risk_weight)
    if len(weights) != 1:
        return None
    return next(iter(weights))


def _unsupported_record(
    *,
    source_id: str,
    source_level: str,
    bucket_key: str | None,
    category: DrcRiskClass,
    residual: float,
    reason: str,
) -> DrcCapitalContribution:
    return DrcCapitalContribution(
        contribution_id=f"attr-unsupported-{_slug(source_id)}",
        source_id=source_id,
        source_level=source_level,
        bucket_key=bucket_key,
        category=category,
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.UNSUPPORTED,
        residual=residual,
        reason=reason,
    )


def _residual_record(
    *,
    source_id: str,
    source_level: str,
    bucket_key: str | None,
    category: DrcRiskClass,
    residual: float,
    reason: str,
) -> DrcCapitalContribution:
    return DrcCapitalContribution(
        contribution_id=f"attr-residual-{_slug(source_id)}",
        source_id=source_id,
        source_level=source_level,
        bucket_key=bucket_key,
        category=category,
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.RESIDUAL,
        residual=residual,
        reason=reason,
    )


def _record_sum(records: tuple[DrcCapitalContribution, ...]) -> float:
    return math.fsum((record.contribution or 0.0) + record.residual for record in records)


def _has_branch(record: object, branch_type: BranchType) -> bool:
    branches = getattr(record, "branch_metadata", ())
    return any(BranchType(branch.branch_type) == branch_type for branch in branches)


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("_", "-").replace(":", "-").replace("/", "-")


__all__ = [
    "calculate_drc_attribution",
    "validate_attribution_reconciliation",
]
