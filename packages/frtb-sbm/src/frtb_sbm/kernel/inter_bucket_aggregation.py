"""
Inter-bucket SBM aggregation kernels.

Regulatory traceability:
    Basel MAR21.4(5) — across-bucket delta/vega aggregation.
    Basel MAR21.6 — correlation scenario adjustments.
    SBM-REQ-006.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frtb_sbm.data_models import BucketCapital, SbmScenarioLabel
from frtb_sbm.kernel.bucket_aggregation import IntraBucketAggregationResult
from frtb_sbm.kernel.correlation_scenarios import adjust_correlation_for_scenario
from frtb_sbm.validation import SbmInputError

_MAR21_INTER_BUCKET_CITATION = ("basel_mar21_4_inter_bucket",)


@dataclass(frozen=True)
class InterBucketScenarioResult:
    """Risk-class capital for one correlation scenario."""

    scenario: SbmScenarioLabel
    capital: float
    capital_variance_sum: float
    alternative_sb_used: bool
    bucket_ids: tuple[str, ...]
    bucket_kb_values: tuple[float, ...]
    bucket_sb_values: tuple[float, ...]
    inter_bucket_correlations: tuple[tuple[str, str, float], ...]
    citation_ids: tuple[str, ...]


def aggregate_inter_bucket(
    bucket_results: Sequence[IntraBucketAggregationResult | BucketCapital],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel = SbmScenarioLabel.MEDIUM,
    apply_scenario_adjustment: bool = True,
    citation_ids: tuple[str, ...] = _MAR21_INTER_BUCKET_CITATION,
) -> InterBucketScenarioResult:
    """Aggregate bucket-level positions across buckets for one scenario (MAR21.4 step 5).

    Uses ``K^2 = sum_b Kb^2 + sum_b sum_c gamma_bc Sb Sc`` with ``gamma_bb = 0``.
    When the summed variance is negative, applies the alternative ``Sb`` specification
    from MAR21.4(5)(b).
    Parameters
    ----------
    bucket_results, inter_bucket_correlations, scenario, apply_scenario_adjustment, citation_ids :
        See function signature for types and defaults.

    Returns
    -------
    InterBucketScenarioResult
    """
    buckets = [_as_bucket_capital(item) for item in bucket_results]
    if not buckets:
        raise SbmInputError("bucket_results must not be empty", field="bucket_results")

    bucket_ids = tuple(sorted({bucket.bucket_id for bucket in buckets}, key=str))
    if len(bucket_ids) != len(buckets):
        raise SbmInputError(
            "duplicate bucket_id values are not permitted in inter-bucket aggregation",
            field="bucket_results",
        )

    kb_values = np.array([bucket.kb for bucket in buckets], dtype=np.float64)
    sb_values = np.array([_bucket_sb(bucket) for bucket in buckets], dtype=np.float64)
    gamma = _build_inter_bucket_gamma_matrix(
        bucket_ids=bucket_ids,
        inter_bucket_correlations=inter_bucket_correlations,
        scenario=scenario,
        apply_scenario_adjustment=apply_scenario_adjustment,
    )

    capital_variance, alternative_sb_used = _inter_bucket_variance(
        kb_values=kb_values,
        sb_values=sb_values,
        gamma=gamma,
    )
    capital = math.sqrt(max(0.0, capital_variance))
    adjusted_correlations = _inter_bucket_correlation_audit(
        bucket_ids=bucket_ids,
        inter_bucket_correlations=inter_bucket_correlations,
        scenario=scenario,
        apply_scenario_adjustment=apply_scenario_adjustment,
    )

    return InterBucketScenarioResult(
        scenario=scenario,
        capital=capital,
        capital_variance_sum=capital_variance,
        alternative_sb_used=alternative_sb_used,
        bucket_ids=bucket_ids,
        bucket_kb_values=tuple(float(value) for value in kb_values),
        bucket_sb_values=tuple(float(value) for value in sb_values),
        inter_bucket_correlations=adjusted_correlations,
        citation_ids=citation_ids,
    )


def _inter_bucket_variance(
    *,
    kb_values: npt.NDArray[np.float64],
    sb_values: npt.NDArray[np.float64],
    gamma: npt.NDArray[np.float64],
) -> tuple[float, bool]:
    variance = float(np.dot(kb_values, kb_values) + sb_values @ gamma @ sb_values)
    if variance >= 0.0:
        return variance, False

    adjusted_sb = np.array(
        [max(min(sb, kb), -kb) for sb, kb in zip(sb_values, kb_values, strict=True)],
        dtype=np.float64,
    )
    adjusted_variance = float(np.dot(kb_values, kb_values) + adjusted_sb @ gamma @ adjusted_sb)
    return adjusted_variance, True


def _build_inter_bucket_gamma_matrix(
    *,
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    scenario: SbmScenarioLabel,
    apply_scenario_adjustment: bool,
) -> npt.NDArray[np.float64]:
    size = len(bucket_ids)
    gamma = np.zeros((size, size), dtype=np.float64)
    index = {bucket_id: position for position, bucket_id in enumerate(bucket_ids)}

    for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items()):
        if bucket_a not in index or bucket_b not in index:
            continue
        applied = (
            adjust_correlation_for_scenario(base_gamma, scenario)
            if apply_scenario_adjustment
            else base_gamma
        )
        row = index[bucket_a]
        col = index[bucket_b]
        gamma[row, col] = applied
        if row != col:
            gamma[col, row] = applied
    return gamma


def _inter_bucket_correlation_audit(
    *,
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    scenario: SbmScenarioLabel,
    apply_scenario_adjustment: bool,
) -> tuple[tuple[str, str, float], ...]:
    audit: list[tuple[str, str, float]] = []
    for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items()):
        if bucket_a not in bucket_ids or bucket_b not in bucket_ids:
            continue
        applied = (
            adjust_correlation_for_scenario(base_gamma, scenario)
            if apply_scenario_adjustment
            else base_gamma
        )
        audit.append((bucket_a, bucket_b, applied))
    return tuple(audit)


def _as_bucket_capital(
    item: IntraBucketAggregationResult | BucketCapital,
) -> BucketCapital:
    if isinstance(item, IntraBucketAggregationResult):
        return item.bucket_capital
    return item


def _bucket_sb(bucket: BucketCapital) -> float:
    if bucket.sb is not None:
        return bucket.sb
    return float(sum(item.scaled_amount for item in bucket.weighted_sensitivities))


__all__ = ["InterBucketScenarioResult", "aggregate_inter_bucket"]
