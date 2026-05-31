"""
SA-CVA shared intra-bucket and inter-bucket aggregation.
"""

from __future__ import annotations

import math
from collections import defaultdict

from frtb_cva.data_models import (
    SaCvaBucketCapital,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
    SaCvaWeightedSensitivity,
)
from frtb_cva.reference_data import (
    girr_delta_intra_bucket_correlation,
    girr_inter_bucket_correlation,
)
from frtb_cva.validation import CvaInputError

HEDGING_DISALLOWANCE_R = 0.01
M_CVA_DEFAULT = 1.0


def _positive_part(value: float) -> float:
    return max(value, 0.0)


def _negative_part(value: float) -> float:
    return min(value, 0.0)


def _hedging_disallowance_term(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
) -> float:
    total = 0.0
    for item in weighted_sensitivities:
        total += _positive_part(item.weighted_cva) * _negative_part(
            item.weighted_hedge
        ) + _negative_part(item.weighted_cva) * _positive_part(item.weighted_hedge)
    return HEDGING_DISALLOWANCE_R * total


def aggregate_intra_bucket(
    bucket_id: str,
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
) -> SaCvaBucketCapital:
    """Aggregate weighted sensitivities to bucket capital K_b."""

    if not weighted_sensitivities:
        raise CvaInputError("bucket requires at least one weighted sensitivity", field="bucket_id")

    variance = 0.0
    for index, left in enumerate(weighted_sensitivities):
        variance += left.weighted_net * left.weighted_net
        for right in weighted_sensitivities[index + 1 :]:
            tenor_left = left.risk_factor_key.tenor or left.risk_factor_key.risk_factor_key
            tenor_right = right.risk_factor_key.tenor or right.risk_factor_key.risk_factor_key
            rho, _ = girr_delta_intra_bucket_correlation(tenor_left, tenor_right)
            variance += 2.0 * rho * left.weighted_net * right.weighted_net
    variance += _hedging_disallowance_term(weighted_sensitivities)
    k_b = math.sqrt(max(variance, 0.0))
    s_b = sum(item.weighted_net for item in weighted_sensitivities)
    floor_applied = abs(s_b) > k_b
    if floor_applied:
        s_b = math.copysign(k_b, s_b) if s_b != 0.0 else 0.0
    return SaCvaBucketCapital(
        bucket_id=bucket_id,
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        k_b=k_b,
        s_b=s_b,
        sensitivity_ids=(),
        citations=("basel_mar50_53", "basel_mar50_56"),
        branch_metadata=(("floor_applied", str(floor_applied)),),
    )


def aggregate_inter_bucket(
    bucket_capitals: tuple[SaCvaBucketCapital, ...],
    *,
    m_cva: float = M_CVA_DEFAULT,
) -> SaCvaRiskClassCapital:
    """Aggregate bucket capitals to GIRR delta risk-class capital."""

    if not bucket_capitals:
        raise CvaInputError("risk class requires at least one bucket", field="bucket_capitals")

    gamma_bc, gamma_citation = girr_inter_bucket_correlation()
    cross_term = 0.0
    sum_kb_squared = 0.0
    for index, left in enumerate(bucket_capitals):
        sum_kb_squared += left.k_b * left.k_b
        for right in bucket_capitals[index + 1 :]:
            cross_term += 2.0 * gamma_bc * left.s_b * right.s_b
    pre_multiplier = math.sqrt(max(sum_kb_squared + cross_term, 0.0))
    post_multiplier = m_cva * pre_multiplier
    return SaCvaRiskClassCapital(
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        pre_multiplier_capital=pre_multiplier,
        post_multiplier_capital=post_multiplier,
        m_cva=m_cva,
        bucket_capitals=bucket_capitals,
        citations=(gamma_citation, "basel_mar50_53"),
    )


def aggregate_weighted_sensitivities(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
    *,
    m_cva: float = M_CVA_DEFAULT,
) -> SaCvaRiskClassCapital:
    """Group weighted sensitivities by bucket and aggregate to risk-class capital."""

    buckets: dict[str, list[SaCvaWeightedSensitivity]] = defaultdict(list)
    for item in weighted_sensitivities:
        buckets[item.risk_factor_key.bucket_id].append(item)
    bucket_capitals = tuple(
        aggregate_intra_bucket(
            bucket_id,
            tuple(sorted(items, key=lambda entry: entry.risk_factor_key.risk_factor_key)),
        )
        for bucket_id, items in sorted(buckets.items())
    )
    return aggregate_inter_bucket(bucket_capitals, m_cva=m_cva)


__all__ = [
    "HEDGING_DISALLOWANCE_R",
    "M_CVA_DEFAULT",
    "aggregate_inter_bucket",
    "aggregate_intra_bucket",
    "aggregate_weighted_sensitivities",
]
