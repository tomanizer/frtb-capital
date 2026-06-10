"""DRC attribution over an already calculated capital result."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from frtb_common import dataclass_as_dict
from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus

from frtb_drc._identifiers import slug_path as _slug
from frtb_drc.data_models import (
    BranchType,
    BucketDrc,
    CategoryDrc,
    DefaultDirection,
    DrcCapitalResult,
    DrcRiskClass,
    NetJtd,
)
from frtb_drc.validation import DrcInputError

_TOLERANCE = 1e-9
_UNALLOCATED_KEY = "UNALLOCATED"
_UNCATEGORISED_KEY = "UNCATEGORISED"


class DrcAttributionGrain(StrEnum):
    """Supported DRC attribution summary grains."""

    ISSUER = "issuer"
    BUCKET = "bucket"
    CATEGORY = "category"
    RISK_CLASS = "risk_class"


@dataclass(frozen=True)
class DrcAttributionSummary:
    """Deterministic grouped projection of DRC attribution records.

    Parameters
    ----------
    summary_id : str
        Stable identifier derived from the grain and grouped key.
    grain : DrcAttributionGrain
        Grouping grain used for the projection.
    key : str
        Grouping key, such as issuer, bucket, category, or risk class.
    risk_class : str | None
        Risk class represented by the group when unique.
    bucket_key : str | None
        Bucket represented by the group when unique.
    contribution : float
        Sum of non-null analytical contribution amounts.
    residual : float
        Sum of residual amounts, including unsupported records.
    total : float
        ``contribution + residual``.
    record_count : int
        Number of source ``CapitalContribution`` records in the group.
    source_ids : tuple[str, ...]
        Deterministic source contribution identifiers included in the group.
    net_jtd_ids : tuple[str, ...]
        Net-JTD source ids included in the group.
    methods : tuple[str, ...]
        Attribution methods present in the group.
    citations : tuple[str, ...]
        Union of source citations.
    reasons : tuple[str, ...]
        Stable non-empty reason strings represented by the group.
    reconciliation_status : ReconciliationStatus
        Reconciliation state implied by the grouped source records.
    """

    summary_id: str
    grain: DrcAttributionGrain
    key: str
    risk_class: str | None
    bucket_key: str | None
    contribution: float
    residual: float
    total: float
    record_count: int
    source_ids: tuple[str, ...]
    net_jtd_ids: tuple[str, ...]
    methods: tuple[str, ...]
    citations: tuple[str, ...]
    reasons: tuple[str, ...]
    reconciliation_status: ReconciliationStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "net_jtd_ids", tuple(self.net_jtd_ids))
        object.__setattr__(self, "methods", tuple(self.methods))
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary representation.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through the shared serializer.
        """

        return dataclass_as_dict(self)


def calculate_drc_attribution(
    result: DrcCapitalResult,
    *,
    risk_weights_by_position: Mapping[str, float],
    tolerance: float = _TOLERANCE,
    input_hash: str = "",
    profile_hash: str = "",
) -> tuple[CapitalContribution, ...]:
    """Calculate deterministic DRC attribution records without changing capital.

    Parameters
    ----------
    result:
        A fully populated ``DrcCapitalResult`` from a completed calculation run.
    risk_weights_by_position:
        Position-level risk weights used to decompose bucket capital via
        analytical Euler attribution.
    tolerance:
        Absolute tolerance for the reconciliation check.
    input_hash:
        Hash of the canonical input snapshot to carry into each
        ``CapitalContribution`` record for downstream audit traceability.
        Pass ``result.input_hash`` when available.
    profile_hash:
        Hash of the rule profile used in the calculation.
        Pass ``result.profile_hash`` when available.

    Returns
    -------
    tuple[CapitalContribution, ...]
        Deterministic attribution records reconciled to ``result.total_drc``.
    """

    net_by_id = {record.net_jtd_id: record for record in result.net_jtds}
    records: list[CapitalContribution] = []
    for category in result.categories:
        records.extend(
            _category_contributions(
                category,
                net_by_id=net_by_id,
                risk_weights_by_position=risk_weights_by_position,
                tolerance=tolerance,
                input_hash=input_hash,
                profile_hash=profile_hash,
            )
        )
    validate_attribution_reconciliation(result, tuple(records), tolerance=tolerance)
    return tuple(records)


def validate_attribution_reconciliation(
    result: DrcCapitalResult,
    records: tuple[CapitalContribution, ...] | None = None,
    *,
    tolerance: float = _TOLERANCE,
) -> None:
    """Validate that contributions plus residual records reconcile to total capital.

    Parameters
    ----------
    result : DrcCapitalResult
        Capital result whose ``total_drc`` is the reconciliation target.
    records : tuple[CapitalContribution, ...] | None, optional
        Attribution records to validate; defaults to ``result.attribution_records``.
    tolerance : float, optional
        Absolute tolerance for the reconciliation check.
    """

    attribution_records = result.attribution_records if records is None else records
    total = math.fsum(
        (record.contribution or 0.0) + record.residual for record in attribution_records
    )
    if abs(total - result.total_drc) > tolerance:
        raise DrcInputError("DRC attribution records do not reconcile to total capital")


def summarize_drc_attribution(
    result: DrcCapitalResult,
    *,
    grain: DrcAttributionGrain | str,
    records: Sequence[CapitalContribution] | None = None,
) -> tuple[DrcAttributionSummary, ...]:
    """Group DRC attribution records without recalculating capital.

    Parameters
    ----------
    result : DrcCapitalResult
        Completed DRC result whose retained net-JTD graph supplies issuer and
        risk-class lineage for analytical net-JTD records.
    grain : DrcAttributionGrain | str
        Projection grain: issuer, bucket, category, or risk_class.
    records : Sequence[CapitalContribution] | None, optional
        Source records to summarize. Defaults to ``result.attribution_records``.

    Returns
    -------
    tuple[DrcAttributionSummary, ...]
        Stable-sorted grouped summaries. Records with no issuer or bucket lineage
        are retained under ``UNALLOCATED`` instead of being dropped.
    """

    projection_grain = DrcAttributionGrain(grain)
    attribution_records = tuple(result.attribution_records if records is None else records)
    net_by_id = {record.net_jtd_id: record for record in result.net_jtds}
    grouped: dict[str, list[CapitalContribution]] = {}
    for record in attribution_records:
        key = _grouping_key(record, projection_grain, net_by_id)
        grouped.setdefault(key, []).append(record)

    summaries = tuple(
        _summary_from_records(
            key=key,
            grain=projection_grain,
            records=tuple(items),
            net_by_id=net_by_id,
        )
        for key, items in grouped.items()
    )
    return tuple(sorted(summaries, key=_summary_sort_key))


def summarize_drc_attribution_by_issuer(
    result: DrcCapitalResult,
    *,
    records: Sequence[CapitalContribution] | None = None,
) -> tuple[DrcAttributionSummary, ...]:
    """Return issuer or unallocated DRC attribution summaries.

    Parameters
    ----------
    result : DrcCapitalResult
        Completed DRC result with retained ``net_jtds`` lineage.
    records : Sequence[CapitalContribution] | None, optional
        Source attribution records; defaults to ``result.attribution_records``.

    Returns
    -------
    tuple[DrcAttributionSummary, ...]
        Stable-sorted issuer summaries.
    """

    return summarize_drc_attribution(result, grain=DrcAttributionGrain.ISSUER, records=records)


def summarize_drc_attribution_by_bucket(
    result: DrcCapitalResult,
    *,
    records: Sequence[CapitalContribution] | None = None,
) -> tuple[DrcAttributionSummary, ...]:
    """Return bucket-level DRC attribution summaries.

    Parameters
    ----------
    result : DrcCapitalResult
        Completed DRC result.
    records : Sequence[CapitalContribution] | None, optional
        Source attribution records; defaults to ``result.attribution_records``.

    Returns
    -------
    tuple[DrcAttributionSummary, ...]
        Stable-sorted bucket summaries.
    """

    return summarize_drc_attribution(result, grain=DrcAttributionGrain.BUCKET, records=records)


def summarize_drc_attribution_by_category(
    result: DrcCapitalResult,
    *,
    records: Sequence[CapitalContribution] | None = None,
) -> tuple[DrcAttributionSummary, ...]:
    """Return DRC category summaries.

    DRC result categories currently align to risk-class capital stacks, but this
    helper is kept separate so report callers can depend on an explicit category
    projection contract.

    Parameters
    ----------
    result : DrcCapitalResult
        Completed DRC result.
    records : Sequence[CapitalContribution] | None, optional
        Source attribution records; defaults to ``result.attribution_records``.

    Returns
    -------
    tuple[DrcAttributionSummary, ...]
        Stable-sorted category summaries.
    """

    return summarize_drc_attribution(result, grain=DrcAttributionGrain.CATEGORY, records=records)


def summarize_drc_attribution_by_risk_class(
    result: DrcCapitalResult,
    *,
    records: Sequence[CapitalContribution] | None = None,
) -> tuple[DrcAttributionSummary, ...]:
    """Return DRC risk-class summaries.

    Parameters
    ----------
    result : DrcCapitalResult
        Completed DRC result with retained net-JTD lineage.
    records : Sequence[CapitalContribution] | None, optional
        Source attribution records; defaults to ``result.attribution_records``.

    Returns
    -------
    tuple[DrcAttributionSummary, ...]
        Stable-sorted risk-class summaries.
    """

    return summarize_drc_attribution(result, grain=DrcAttributionGrain.RISK_CLASS, records=records)


def top_drc_attribution_summaries(
    result: DrcCapitalResult,
    *,
    grain: DrcAttributionGrain | str,
    limit: int = 10,
    records: Sequence[CapitalContribution] | None = None,
) -> tuple[DrcAttributionSummary, ...]:
    """Return the largest DRC attribution summary groups by absolute total.

    Parameters
    ----------
    result : DrcCapitalResult
        Completed DRC result.
    grain : DrcAttributionGrain | str
        Projection grain: issuer, bucket, category, or risk_class.
    limit : int, optional
        Maximum number of groups to return. Must be non-negative.
    records : Sequence[CapitalContribution] | None, optional
        Source attribution records; defaults to ``result.attribution_records``.

    Returns
    -------
    tuple[DrcAttributionSummary, ...]
        Stable top-contributor summaries.

    Raises
    ------
    ValueError
        If ``limit`` is negative.
    """

    if limit < 0:
        raise ValueError("limit must be non-negative")
    return summarize_drc_attribution(result, grain=grain, records=records)[:limit]


def _category_contributions(
    category: CategoryDrc,
    *,
    net_by_id: Mapping[str, NetJtd],
    risk_weights_by_position: Mapping[str, float],
    tolerance: float,
    input_hash: str,
    profile_hash: str,
) -> tuple[CapitalContribution, ...]:
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
                input_hash=input_hash,
                profile_hash=profile_hash,
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
                input_hash=input_hash,
                profile_hash=profile_hash,
            ),
        )

    bucket_factors = _bucket_category_factors(category)
    records: list[CapitalContribution] = []
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
            input_hash=input_hash,
            profile_hash=profile_hash,
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
                input_hash=input_hash,
                profile_hash=profile_hash,
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
    input_hash: str,
    profile_hash: str,
) -> tuple[CapitalContribution, ...]:
    if bucket.floor_applied or _has_branch(bucket, BranchType.FLOOR):
        return (
            _unsupported_record(
                source_id=bucket.bucket_id,
                source_level="bucket",
                bucket_key=bucket.bucket_key,
                category=category,
                residual=category_factor * bucket.capital,
                reason="bucket floor makes exact Euler attribution unsupported",
                citations=bucket.citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
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
                citations=bucket.citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
            ),
        )

    aggregate_long = bucket.hbr.aggregate_net_long
    aggregate_short = bucket.hbr.aggregate_net_short
    denominator_sq = bucket.hbr.denominator * bucket.hbr.denominator
    records: list[CapitalContribution] = []
    for net_jtd_id in bucket.net_jtd_ids:
        net_jtd = net_by_id.get(net_jtd_id)
        if net_jtd is None:
            return (
                _unsupported_record(
                    source_id=bucket.bucket_id,
                    source_level="bucket",
                    bucket_key=bucket.bucket_key,
                    category=category,
                    residual=category_factor * bucket.capital,
                    reason="net JTD record is missing; exact Euler attribution is unsupported",
                    citations=bucket.citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                ),
            )
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
                    citations=bucket.citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
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
            CapitalContribution(
                contribution_id=f"attr-{_slug(net_jtd.net_jtd_id)}",
                source_id=net_jtd.net_jtd_id,
                source_level="net_jtd",
                bucket_key=bucket.bucket_key,
                category=str(category),
                base_amount=net_jtd.net_amount,
                marginal_multiplier=multiplier,
                contribution=contribution,
                method=AttributionMethod.ANALYTICAL_EULER,
                reason="analytical Euler over stable DRC bucket/category branch",
                citations=bucket.citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=ReconciliationStatus.RECONCILED,
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
    citations: tuple[str, ...] = (),
    input_hash: str = "",
    profile_hash: str = "",
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=f"attr-unsupported-{_slug(source_id)}",
        source_id=source_id,
        source_level=source_level,
        bucket_key=bucket_key,
        category=str(category),
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.UNSUPPORTED,
        residual=residual,
        reason=reason,
        citations=citations,
        input_hash=input_hash,
        profile_hash=profile_hash,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )


def _residual_record(
    *,
    source_id: str,
    source_level: str,
    bucket_key: str | None,
    category: DrcRiskClass,
    residual: float,
    reason: str,
    citations: tuple[str, ...] = (),
    input_hash: str = "",
    profile_hash: str = "",
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=f"attr-residual-{_slug(source_id)}",
        source_id=source_id,
        source_level=source_level,
        bucket_key=bucket_key,
        category=str(category),
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.RESIDUAL,
        residual=residual,
        reason=reason,
        citations=citations,
        input_hash=input_hash,
        profile_hash=profile_hash,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )


def _record_sum(records: tuple[CapitalContribution, ...]) -> float:
    return math.fsum((record.contribution or 0.0) + record.residual for record in records)


def _has_branch(record: object, branch_type: BranchType) -> bool:
    branches = getattr(record, "branch_metadata", ())
    return any(BranchType(branch.branch_type) == branch_type for branch in branches)


def _grouping_key(
    record: CapitalContribution,
    grain: DrcAttributionGrain,
    net_by_id: Mapping[str, NetJtd],
) -> str:
    if grain == DrcAttributionGrain.ISSUER:
        if record.source_level == "net_jtd":
            net_jtd = net_by_id.get(record.source_id)
            if net_jtd is not None and net_jtd.obligor_or_tranche_key:
                return net_jtd.obligor_or_tranche_key
        return _UNALLOCATED_KEY
    if grain == DrcAttributionGrain.BUCKET:
        return record.bucket_key or _UNALLOCATED_KEY
    if grain == DrcAttributionGrain.CATEGORY:
        return record.category or _UNCATEGORISED_KEY
    if grain == DrcAttributionGrain.RISK_CLASS:
        if record.source_level == "net_jtd":
            net_jtd = net_by_id.get(record.source_id)
            if net_jtd is not None:
                return str(net_jtd.risk_class)
        return record.category or _UNCATEGORISED_KEY
    raise ValueError(f"unsupported DRC attribution grain: {grain}")


def _summary_from_records(
    *,
    key: str,
    grain: DrcAttributionGrain,
    records: tuple[CapitalContribution, ...],
    net_by_id: Mapping[str, NetJtd],
) -> DrcAttributionSummary:
    contribution = math.fsum(
        0.0 if record.contribution is None else record.contribution for record in records
    )
    residual = math.fsum(record.residual for record in records)
    source_ids = _sorted_unique(record.source_id for record in records)
    net_jtd_ids = _sorted_unique(
        record.source_id for record in records if record.source_level == "net_jtd"
    )
    risk_classes = _sorted_unique(_record_risk_class(record, net_by_id) for record in records)
    bucket_keys = _sorted_unique(record.bucket_key for record in records if record.bucket_key)
    return DrcAttributionSummary(
        summary_id=f"drc-attr-{grain.value}-{_summary_slug(key)}",
        grain=grain,
        key=key,
        risk_class=risk_classes[0] if len(risk_classes) == 1 else None,
        bucket_key=bucket_keys[0] if len(bucket_keys) == 1 else None,
        contribution=contribution,
        residual=residual,
        total=contribution + residual,
        record_count=len(records),
        source_ids=source_ids,
        net_jtd_ids=net_jtd_ids,
        methods=_sorted_unique(str(record.method) for record in records),
        citations=_sorted_unique(citation for record in records for citation in record.citations),
        reasons=_sorted_unique(record.reason for record in records if record.reason),
        reconciliation_status=_summary_status(records),
    )


def _record_risk_class(
    record: CapitalContribution,
    net_by_id: Mapping[str, NetJtd],
) -> str:
    net_jtd = net_by_id.get(record.source_id) if record.source_level == "net_jtd" else None
    return str(net_jtd.risk_class) if net_jtd is not None else record.category


def _summary_status(records: tuple[CapitalContribution, ...]) -> ReconciliationStatus:
    statuses = {ReconciliationStatus(record.reconciliation_status) for record in records}
    if ReconciliationStatus.UNRECONCILED in statuses:
        return ReconciliationStatus.UNRECONCILED
    residual_methods = {AttributionMethod.RESIDUAL, AttributionMethod.UNSUPPORTED}
    if any(record.method in residual_methods for record in records):
        return ReconciliationStatus.PARTIAL_RESIDUAL
    if any(abs(record.residual) > 0.0 for record in records):
        return ReconciliationStatus.PARTIAL_RESIDUAL
    if statuses == {ReconciliationStatus.RECONCILED}:
        return ReconciliationStatus.RECONCILED
    if ReconciliationStatus.PARTIAL_RESIDUAL in statuses:
        return ReconciliationStatus.PARTIAL_RESIDUAL
    return ReconciliationStatus.UNKNOWN


def _summary_sort_key(summary: DrcAttributionSummary) -> tuple[float, str, str, str]:
    return (-abs(summary.total), summary.grain.value, summary.key, summary.summary_id)


def _summary_slug(value: str) -> str:
    return _slug(value).replace("|", "-")


def _sorted_unique(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value is not None and str(value) != ""}))


__all__ = [
    "DrcAttributionGrain",
    "DrcAttributionSummary",
    "calculate_drc_attribution",
    "summarize_drc_attribution",
    "summarize_drc_attribution_by_bucket",
    "summarize_drc_attribution_by_category",
    "summarize_drc_attribution_by_issuer",
    "summarize_drc_attribution_by_risk_class",
    "top_drc_attribution_summaries",
    "validate_attribution_reconciliation",
]
