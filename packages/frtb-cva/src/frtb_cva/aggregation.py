"""
SA-CVA shared intra-bucket and inter-bucket aggregation.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from frtb_cva.data_models import (
    CvaRegulatoryProfile,
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
from frtb_cva.validation import CvaInputError, validate_m_cva_multiplier

HEDGING_DISALLOWANCE_R = 0.01
M_CVA_DEFAULT = 1.0


def _hedging_disallowance_term(weighted_hedges: np.ndarray) -> float:
    # MAR50.55 indirect-hedge disallowance: R · Σ_k (WS_k^HDG)². Always
    # non-negative — a partial hedge offsets the net sensitivity term but
    # leaves an R·(WS_HDG)² residual under the square root, so K_b is never
    # driven below sqrt(R)·|WS_HDG|. See ADR 0016 for the derivation and the
    # bug history (the original signed-cross-product form reduced K_b).
    return float(HEDGING_DISALLOWANCE_R * np.dot(weighted_hedges, weighted_hedges))


def _intra_bucket_correlation_matrix(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
    *,
    profile: CvaRegulatoryProfile | str,
) -> np.ndarray:
    count = len(weighted_sensitivities)
    rho_matrix = np.eye(count, dtype=np.float64)
    if count < 2:
        return rho_matrix

    tenors: list[str] = []
    for item in weighted_sensitivities:
        tenor = item.risk_factor_key.tenor
        if tenor is None:
            raise CvaInputError(
                "GIRR delta intra-bucket aggregation requires tenor",
                field="tenor",
            )
        tenors.append(tenor)

    for left_index in range(count):
        for right_index in range(left_index + 1, count):
            rho, _ = girr_delta_intra_bucket_correlation(
                tenors[left_index],
                tenors[right_index],
                profile=profile,
            )
            rho_matrix[left_index, right_index] = rho
            rho_matrix[right_index, left_index] = rho
    return rho_matrix


def aggregate_intra_bucket(
    bucket_id: str,
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaBucketCapital:
    """Aggregate weighted sensitivities to bucket capital K_b."""

    if not weighted_sensitivities:
        raise CvaInputError("bucket requires at least one weighted sensitivity", field="bucket_id")

    weighted_nets = np.fromiter(
        (item.weighted_net for item in weighted_sensitivities),
        dtype=np.float64,
        count=len(weighted_sensitivities),
    )
    weighted_hedges = np.fromiter(
        (item.weighted_hedge for item in weighted_sensitivities),
        dtype=np.float64,
        count=len(weighted_sensitivities),
    )
    rho_matrix = _intra_bucket_correlation_matrix(weighted_sensitivities, profile=profile)
    variance = float(weighted_nets @ rho_matrix @ weighted_nets) + _hedging_disallowance_term(
        weighted_hedges
    )
    k_b = math.sqrt(max(variance, 0.0))
    s_b = float(np.sum(weighted_nets))
    floor_applied = abs(s_b) > k_b
    if floor_applied:
        s_b = math.copysign(k_b, s_b) if s_b != 0.0 else 0.0
    sensitivity_ids = tuple(
        sorted(
            {
                sensitivity_id
                for item in weighted_sensitivities
                for sensitivity_id in item.source_sensitivity_ids
            }
        )
    )
    return SaCvaBucketCapital(
        bucket_id=bucket_id,
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        k_b=k_b,
        s_b=s_b,
        sensitivity_ids=sensitivity_ids,
        citations=("basel_mar50_53", "basel_mar50_56"),
        branch_metadata=(("floor_applied", str(floor_applied)),),
    )


def aggregate_inter_bucket(
    bucket_capitals: tuple[SaCvaBucketCapital, ...],
    *,
    m_cva: float = M_CVA_DEFAULT,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Aggregate bucket capitals to GIRR delta risk-class capital."""

    if not bucket_capitals:
        raise CvaInputError("risk class requires at least one bucket", field="bucket_capitals")

    validated_m_cva = validate_m_cva_multiplier(m_cva)
    gamma_bc, gamma_citation = girr_inter_bucket_correlation(profile=profile)
    bucket_count = len(bucket_capitals)
    bucket_kb = np.fromiter(
        (bucket.k_b for bucket in bucket_capitals),
        dtype=np.float64,
        count=bucket_count,
    )
    bucket_sb = np.fromiter(
        (bucket.s_b for bucket in bucket_capitals),
        dtype=np.float64,
        count=bucket_count,
    )
    sum_kb_squared = float(np.dot(bucket_kb, bucket_kb))
    sum_sb = float(bucket_sb.sum())
    sum_sb_squared = float(np.dot(bucket_sb, bucket_sb))
    cross_term = gamma_bc * (sum_sb * sum_sb - sum_sb_squared)
    pre_multiplier = math.sqrt(max(sum_kb_squared + cross_term, 0.0))
    post_multiplier = validated_m_cva * pre_multiplier
    return SaCvaRiskClassCapital(
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        pre_multiplier_capital=pre_multiplier,
        post_multiplier_capital=post_multiplier,
        m_cva=validated_m_cva,
        bucket_capitals=bucket_capitals,
        citations=(gamma_citation, "basel_mar50_53"),
    )


def aggregate_weighted_sensitivities(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
    *,
    m_cva: float = M_CVA_DEFAULT,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Group weighted sensitivities by bucket and aggregate to risk-class capital."""

    buckets: dict[str, list[SaCvaWeightedSensitivity]] = defaultdict(list)
    for item in weighted_sensitivities:
        buckets[item.risk_factor_key.bucket_id].append(item)
    bucket_capitals = tuple(
        aggregate_intra_bucket(
            bucket_id,
            tuple(sorted(items, key=lambda entry: entry.risk_factor_key.risk_factor_key)),
            profile=profile,
        )
        for bucket_id, items in sorted(buckets.items())
    )
    return aggregate_inter_bucket(bucket_capitals, m_cva=m_cva, profile=profile)


__all__ = [
    "HEDGING_DISALLOWANCE_R",
    "M_CVA_DEFAULT",
    "aggregate_inter_bucket",
    "aggregate_intra_bucket",
    "aggregate_weighted_sensitivities",
]
