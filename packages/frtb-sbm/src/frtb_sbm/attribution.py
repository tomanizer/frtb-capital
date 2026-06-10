"""
Analytical Euler capital contribution attribution for SBM delta and vega.

Regulatory traceability:
    Basel MAR21.4(4)-(5) — intra- and inter-bucket aggregation (Euler basis).
    Basel MAR21.5       — curvature: CVR max(⋅,0) floor → UNSUPPORTED.
    ADR 0038            — suite-wide attribution and impact contract.
    ADR 0037            — analytical Euler decomposition framework.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from frtb_common.attribution import (
    AttributionMethod,
    CapitalContribution,
    ReconciliationStatus,
)
from frtb_common.serialization import dataclass_as_dict

from frtb_sbm.data_models import (
    BucketCapital,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmCapitalResult,
    SbmRiskMeasure,
    WeightedSensitivity,
)

_RECONCILIATION_TOLERANCE = 1e-6
_UNALLOCATED_KEY = "UNALLOCATED"
_UNCATEGORISED_KEY = "UNCATEGORISED"

# Citation IDs carried on every SBM attribution record.
_ATTRIBUTION_CITATIONS = (
    "basel_mar21_4_intra_bucket",
    "basel_mar21_4_inter_bucket",
    "adr_0037",
    "adr_0038",
)


class SbmAttributionGrain(StrEnum):
    """Supported SBM attribution summary grains."""

    SENSITIVITY = "sensitivity"
    BUCKET = "bucket"
    RISK_CLASS = "risk_class"


@dataclass(frozen=True)
class SbmAttributionSummary:
    """Deterministic grouped projection of SBM attribution records.

    Parameters
    ----------
    summary_id : str
        Stable identifier derived from the grain and grouped key.
    grain : SbmAttributionGrain
        Grouping grain used for the projection.
    key : str
        Grouping key, such as sensitivity id, bucket, or risk class.
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
        Deterministic source identifiers included in the group.
    sensitivity_ids : tuple[str, ...]
        Sensitivity source ids included in the group.
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
    grain: SbmAttributionGrain
    key: str
    risk_class: str | None
    bucket_key: str | None
    contribution: float
    residual: float
    total: float
    record_count: int
    source_ids: tuple[str, ...]
    sensitivity_ids: tuple[str, ...]
    methods: tuple[str, ...]
    citations: tuple[str, ...]
    reasons: tuple[str, ...]
    reconciliation_status: ReconciliationStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "sensitivity_ids", tuple(self.sensitivity_ids))
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


def calculate_sbm_attribution(
    result: SbmCapitalResult,
) -> tuple[CapitalContribution, ...]:
    """Return analytical Euler contributions for all delta and vega risk classes.

    Curvature risk classes are returned as ``UNSUPPORTED`` records because the
    CVR max(⋅,0) floor prevents exact Euler decomposition (MAR21.5).

    Attribution records are at sensitivity granularity for analytical Euler
    paths and at risk-class granularity for unsupported paths.  The sum of
    ``(contribution or 0) + residual`` across all returned records equals
    ``result.total_capital`` when all risk classes use the analytical path.
    """
    records: list[CapitalContribution] = []
    for rc in result.risk_classes:
        records.extend(_risk_class_contributions(rc, result.input_hash, result.profile_hash))
    return tuple(records)


def summarize_sbm_attribution(
    records: Sequence[CapitalContribution],
    *,
    grain: SbmAttributionGrain | str,
) -> tuple[SbmAttributionSummary, ...]:
    """Group SBM attribution records without recalculating capital or attribution.

    Parameters
    ----------
    records : Sequence[CapitalContribution]
        Source records returned by ``calculate_sbm_attribution`` or an equivalent
        persisted attribution view.
    grain : SbmAttributionGrain | str
        Projection grain: sensitivity, bucket, or risk_class.

    Returns
    -------
    tuple[SbmAttributionSummary, ...]
        Stable-sorted grouped summaries. Unsupported and residual records are
        retained under their source id or an unallocated bucket instead of being
        dropped.
    """

    projection_grain = SbmAttributionGrain(grain)
    grouped: dict[str, list[CapitalContribution]] = {}
    for record in records:
        key = _grouping_key(record, projection_grain)
        grouped.setdefault(key, []).append(record)

    summaries = tuple(
        _summary_from_records(
            key=key,
            grain=projection_grain,
            records=tuple(items),
        )
        for key, items in grouped.items()
    )
    return tuple(sorted(summaries, key=_summary_sort_key))


def summarize_sbm_attribution_by_sensitivity(
    records: Sequence[CapitalContribution],
) -> tuple[SbmAttributionSummary, ...]:
    """Return sensitivity/source-level SBM attribution summaries.

    Parameters
    ----------
    records : Sequence[CapitalContribution]
        Source attribution records.

    Returns
    -------
    tuple[SbmAttributionSummary, ...]
        Stable-sorted sensitivity summaries.
    """

    return summarize_sbm_attribution(records, grain=SbmAttributionGrain.SENSITIVITY)


def summarize_sbm_attribution_by_bucket(
    records: Sequence[CapitalContribution],
) -> tuple[SbmAttributionSummary, ...]:
    """Return bucket-level SBM attribution summaries.

    Parameters
    ----------
    records : Sequence[CapitalContribution]
        Source attribution records.

    Returns
    -------
    tuple[SbmAttributionSummary, ...]
        Stable-sorted bucket summaries.
    """

    return summarize_sbm_attribution(records, grain=SbmAttributionGrain.BUCKET)


def summarize_sbm_attribution_by_risk_class(
    records: Sequence[CapitalContribution],
) -> tuple[SbmAttributionSummary, ...]:
    """Return risk-class-level SBM attribution summaries.

    Parameters
    ----------
    records : Sequence[CapitalContribution]
        Source attribution records.

    Returns
    -------
    tuple[SbmAttributionSummary, ...]
        Stable-sorted risk-class summaries.
    """

    return summarize_sbm_attribution(records, grain=SbmAttributionGrain.RISK_CLASS)


def top_sbm_attribution_summaries(
    records: Sequence[CapitalContribution],
    *,
    grain: SbmAttributionGrain | str,
    limit: int = 10,
) -> tuple[SbmAttributionSummary, ...]:
    """Return the largest SBM attribution summary groups by absolute total.

    Parameters
    ----------
    records : Sequence[CapitalContribution]
        Source attribution records.
    grain : SbmAttributionGrain | str
        Projection grain: sensitivity, bucket, or risk_class.
    limit : int, optional
        Maximum number of groups to return. Must be non-negative.

    Returns
    -------
    tuple[SbmAttributionSummary, ...]
        Stable top-contributor summaries.

    Raises
    ------
    ValueError
        If ``limit`` is negative.
    """

    if limit < 0:
        raise ValueError("limit must be non-negative")
    return summarize_sbm_attribution(records, grain=grain)[:limit]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _risk_class_contributions(
    rc: RiskClassCapital,
    input_hash: str,
    profile_hash: str,
) -> list[CapitalContribution]:
    source_id = f"{rc.risk_class}:{rc.risk_measure}"
    citations = _ATTRIBUTION_CITATIONS + tuple(rc.citation_ids)

    # Curvature: CVR max(⋅,0) prevents analytical Euler decomposition.
    if rc.risk_measure is SbmRiskMeasure.CURVATURE:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason=(
                    "Curvature capital: CVR max(⋅,0) floor prevents exact Euler "
                    "decomposition (MAR21.5). See ADR 0038."
                ),
            )
        ]

    capital = rc.selected_capital
    if capital == 0.0:
        return []

    # Find the selected scenario detail (needed for pairwise correlations and S_b).
    selected_scenario = rc.selected_scenario
    if selected_scenario is None or not rc.scenario_details:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason="No scenario detail retained; cannot reconstruct correlation matrices.",
            )
        ]

    selected_detail: RiskClassScenarioDetail | None = next(
        (d for d in rc.scenario_details if d.scenario == selected_scenario), None
    )
    if selected_detail is None:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason=f"Scenario detail not found for selected scenario {selected_scenario}.",
            )
        ]

    # Alternative S_b (MAR21.4(5)(b)): adjusted values are not retained in the result.
    if selected_detail.alternative_sb_used:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason=(
                    "Alternative S_b specification (MAR21.4(5)(b)) was used; "
                    "adjusted S_b values are not retained for Euler decomposition."
                ),
            )
        ]

    intra_by_bucket: dict[str, IntraBucketScenarioRecord] = {
        rec.bucket_id: rec for rec in selected_detail.intra_buckets
    }

    # Partial pairwise materialisation: correlation matrix cannot be reconstructed.
    for intra_check in intra_by_bucket.values():
        summary = intra_check.pairwise_correlation_summary
        if summary is not None and summary.omitted_count > 0:
            return [
                _unsupported_rc(
                    source_id=source_id,
                    rc=rc,
                    citations=citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                    reason=(
                        f"Pairwise correlations not fully materialised for bucket "
                        f"'{intra_check.bucket_id}' "
                        f"({summary.omitted_count} of {summary.total_count} pairs omitted). "
                        "Increase pairwise_evidence_limit to enable full attribution."
                    ),
                )
            ]

    # Any active floor: Euler derivative is undefined at the floor boundary.
    for bucket in rc.buckets:
        if bucket.floor_applied:
            return [
                _unsupported_rc(
                    source_id=source_id,
                    rc=rc,
                    citations=citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                    reason=(
                        f"Floor active in bucket '{bucket.bucket_id}'; "
                        "Euler derivative undefined at floor boundary."
                    ),
                )
            ]

    # All preconditions met -> compute analytical Euler contributions.
    s_by_bucket: dict[str, float] = {rec.bucket_id: rec.sb for rec in selected_detail.intra_buckets}
    gamma_s = _compute_gamma_s(selected_detail.inter_bucket_correlations, s_by_bucket)

    records: list[CapitalContribution] = []
    for bucket in rc.buckets:
        intra: IntraBucketScenarioRecord | None = intra_by_bucket.get(bucket.bucket_id)
        if intra is None:
            records.append(
                _unsupported_rc(
                    source_id=f"{source_id}:{bucket.bucket_id}",
                    rc=rc,
                    citations=citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                    reason=f"Intra-bucket detail missing for bucket '{bucket.bucket_id}'.",
                )
            )
            continue
        gamma_s_a = gamma_s.get(bucket.bucket_id, 0.0)
        records.extend(
            _bucket_euler_contributions(
                bucket=bucket,
                intra=intra,
                capital=capital,
                gamma_s_a=gamma_s_a,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
            )
        )

    # Add a reconciliation residual for floating-point drift (should be negligible).
    total = sum((r.contribution or 0.0) + r.residual for r in records)
    tol = _RECONCILIATION_TOLERANCE * max(abs(capital), 1.0)
    if abs(total - capital) > tol:
        records.append(
            CapitalContribution(
                contribution_id=f"sbm-{source_id}-residual",
                source_id=source_id,
                source_level="risk_class",
                bucket_key=None,
                category=str(rc.risk_class),
                base_amount=0.0,
                marginal_multiplier=None,
                contribution=None,
                method=AttributionMethod.RESIDUAL,
                residual=capital - total,
                reason="Euler decomposition rounding residual.",
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
            )
        )

    return records


def _bucket_euler_contributions(
    *,
    bucket: BucketCapital,
    intra: IntraBucketScenarioRecord,
    capital: float,
    gamma_s_a: float,
    citations: tuple[str, ...],
    input_hash: str,
    profile_hash: str,
) -> list[CapitalContribution]:
    """Euler contributions for every weighted sensitivity in one bucket.

    For sensitivity i in bucket a with capital K:

        marginal_i = [(rho_a @ ws_a)[i] + (gamma @ S)_a] / K
        contribution_i = WS_i * marginal_i

    Euler's theorem guarantees sum(contribution_i) == K when summed over all
    buckets (no floors, complete pairwise materialisation).
    """
    ws_list: tuple[WeightedSensitivity, ...] = bucket.weighted_sensitivities
    if not ws_list:
        return []

    rho_ws = _compute_rho_times_ws(ws_list, intra.pairwise_correlations)

    records: list[CapitalContribution] = []
    for i, ws in enumerate(ws_list):
        numerator_i = rho_ws[i] + gamma_s_a
        marginal = numerator_i / capital
        contribution = ws.scaled_amount * marginal

        sensitivity_citations = citations + tuple(ws.citation_ids)
        records.append(
            CapitalContribution(
                contribution_id=f"sbm-{ws.sensitivity_id}",
                source_id=ws.sensitivity_id,
                source_level="sensitivity",
                bucket_key=bucket.bucket_id,
                category=str(bucket.risk_class),
                base_amount=ws.scaled_amount,
                marginal_multiplier=marginal,
                contribution=contribution,
                method=AttributionMethod.ANALYTICAL_EULER,
                residual=0.0,
                reason="",
                citations=sensitivity_citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=ReconciliationStatus.RECONCILED,
            )
        )
    return records


def _compute_rho_times_ws(
    ws_list: tuple[WeightedSensitivity, ...],
    pairwise: tuple[PairwiseCorrelationRecord, ...],
) -> list[float]:
    """Return the vector (rho @ ws) computed from upper-triangle pairwise records.

    Pairwise records store the upper triangle including the diagonal.  Off-diagonal
    entries are applied symmetrically.
    """
    id_to_index = {ws.sensitivity_id: idx for idx, ws in enumerate(ws_list)}
    ws_values = [ws.scaled_amount for ws in ws_list]
    result = [0.0] * len(ws_list)

    for rec in pairwise:
        i = id_to_index.get(rec.sensitivity_a)
        j = id_to_index.get(rec.sensitivity_b)
        if i is None or j is None:
            continue
        if i == j:
            result[i] += ws_values[i]  # diagonal rho_ii = 1
        else:
            result[i] += rec.correlation * ws_values[j]
            result[j] += rec.correlation * ws_values[i]

    return result


def _compute_gamma_s(
    inter_bucket_correlations: tuple[tuple[str, str, float], ...],
    s_by_bucket: dict[str, float],
) -> dict[str, float]:
    """Compute (gamma @ S) for each bucket from stored upper-triangle gamma records.

    The stored records have one direction per pair (a < b in sorted order).
    Each entry contributes symmetrically to both buckets.
    """
    gamma_s: dict[str, float] = {bid: 0.0 for bid in s_by_bucket}

    for bucket_a, bucket_b, gamma_ab in inter_bucket_correlations:
        if bucket_a == bucket_b:
            continue
        s_a = s_by_bucket.get(bucket_a, 0.0)
        s_b = s_by_bucket.get(bucket_b, 0.0)
        if bucket_a in gamma_s:
            gamma_s[bucket_a] += gamma_ab * s_b
        if bucket_b in gamma_s:
            gamma_s[bucket_b] += gamma_ab * s_a

    return gamma_s


def _unsupported_rc(
    *,
    source_id: str,
    rc: RiskClassCapital,
    citations: tuple[str, ...],
    input_hash: str,
    profile_hash: str,
    reason: str,
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=f"sbm-{source_id}-unsupported",
        source_id=source_id,
        source_level="risk_class",
        bucket_key=None,
        category=str(rc.risk_class),
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.UNSUPPORTED,
        residual=rc.selected_capital,
        reason=reason,
        citations=citations,
        input_hash=input_hash,
        profile_hash=profile_hash,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )


def _grouping_key(record: CapitalContribution, grain: SbmAttributionGrain) -> str:
    if grain == SbmAttributionGrain.SENSITIVITY:
        return record.source_id or _UNALLOCATED_KEY
    if grain == SbmAttributionGrain.BUCKET:
        return record.bucket_key or _UNALLOCATED_KEY
    if grain == SbmAttributionGrain.RISK_CLASS:
        return record.category or _UNCATEGORISED_KEY
    raise ValueError(f"unsupported SBM attribution grain: {grain}")


def _summary_from_records(
    *,
    key: str,
    grain: SbmAttributionGrain,
    records: tuple[CapitalContribution, ...],
) -> SbmAttributionSummary:
    contribution = math.fsum(
        0.0 if record.contribution is None else record.contribution for record in records
    )
    residual = math.fsum(record.residual for record in records)
    bucket_keys = _sorted_unique(record.bucket_key for record in records if record.bucket_key)
    risk_classes = _sorted_unique(record.category for record in records if record.category)
    return SbmAttributionSummary(
        summary_id=f"sbm-attr-{grain.value}-{_summary_slug(key)}",
        grain=grain,
        key=key,
        risk_class=risk_classes[0] if len(risk_classes) == 1 else None,
        bucket_key=bucket_keys[0] if len(bucket_keys) == 1 else None,
        contribution=contribution,
        residual=residual,
        total=contribution + residual,
        record_count=len(records),
        source_ids=_sorted_unique(record.source_id for record in records),
        sensitivity_ids=_sorted_unique(
            record.source_id for record in records if record.source_level == "sensitivity"
        ),
        methods=_sorted_unique(str(record.method) for record in records),
        citations=_sorted_unique(citation for record in records for citation in record.citations),
        reasons=_sorted_unique(record.reason for record in records if record.reason),
        reconciliation_status=_summary_status(records),
    )


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


def _summary_sort_key(summary: SbmAttributionSummary) -> tuple[float, str, str, str]:
    return (-abs(summary.total), summary.grain.value, summary.key, summary.summary_id)


def _summary_slug(value: str) -> str:
    return "-".join(_slug_part(part) for part in str(value).split("|"))


def _slug_part(value: str) -> str:
    chars: list[str] = []
    previous_was_separator = False
    for char in value.strip().lower():
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
        elif not previous_was_separator:
            chars.append("-")
            previous_was_separator = True
    return "".join(chars).strip("-") or "unallocated"


def _sorted_unique(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value is not None and str(value) != ""}))


__all__ = [
    "SbmAttributionGrain",
    "SbmAttributionSummary",
    "calculate_sbm_attribution",
    "summarize_sbm_attribution",
    "summarize_sbm_attribution_by_bucket",
    "summarize_sbm_attribution_by_risk_class",
    "summarize_sbm_attribution_by_sensitivity",
    "top_sbm_attribution_summaries",
]
