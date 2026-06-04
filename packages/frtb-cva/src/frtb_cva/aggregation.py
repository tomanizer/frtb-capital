"""
SA-CVA shared intra-bucket and inter-bucket aggregation.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

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
    profile_citation_id,
    profile_citation_ids,
)
from frtb_cva.sa_cva_reference_data import girr_vega_intra_bucket_correlation
from frtb_cva.validation import CvaInputError, validate_m_cva_multiplier

HEDGING_DISALLOWANCE_R = 0.01
M_CVA_DEFAULT = 1.0

IntraBucketCorrelationFn = Callable[
    [SaCvaWeightedSensitivity, SaCvaWeightedSensitivity],
    tuple[float, str],
]
InterBucketGammaFn = Callable[[str, str], tuple[float, str]]


@dataclass(frozen=True)
class SaCvaAggregationConfig:
    """Risk-class-specific aggregation hooks for MAR50.53."""

    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    intra_bucket_correlation: IntraBucketCorrelationFn
    inter_bucket_gamma: InterBucketGammaFn
    intra_bucket_citations: tuple[str, ...] = ("basel_mar50_53",)


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
    correlation_fn: IntraBucketCorrelationFn,
) -> np.ndarray:
    count = len(weighted_sensitivities)
    rho_matrix = np.eye(count, dtype=np.float64)
    if count < 2:
        return rho_matrix

    for left_index in range(count):
        for right_index in range(left_index + 1, count):
            rho, _ = correlation_fn(
                weighted_sensitivities[left_index],
                weighted_sensitivities[right_index],
            )
            rho_matrix[left_index, right_index] = rho
            rho_matrix[right_index, left_index] = rho
    return rho_matrix


def aggregate_intra_bucket(
    bucket_id: str,
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
    *,
    config: SaCvaAggregationConfig,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaBucketCapital:
    """Aggregate weighted sensitivities to bucket capital K_b.

    Parameters
    ----------
    bucket_id : str
        SA-CVA bucket identifier stored on the bucket capital result.
    weighted_sensitivities : tuple[SaCvaWeightedSensitivity, ...]
        Net and hedge-weighted SA-CVA sensitivities validated for bucket aggregation.
    config : SaCvaAggregationConfig
        Risk-class aggregation hooks (intra-bucket correlation, inter-bucket gamma,
        citation ids).
    profile : CvaRegulatoryProfile | str, optional
        Regulatory profile label or enum value; defaults to Basel MAR50 (2020).

    Returns
    -------
    SaCvaBucketCapital
        Bucket capital ``K_b`` with floor metadata and profile-mapped citations.
    """

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
    rho_matrix = _intra_bucket_correlation_matrix(
        weighted_sensitivities,
        correlation_fn=config.intra_bucket_correlation,
    )
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
        risk_class=config.risk_class,
        risk_measure=config.risk_measure,
        k_b=k_b,
        s_b=s_b,
        sensitivity_ids=sensitivity_ids,
        citations=profile_citation_ids(config.intra_bucket_citations, profile),
        branch_metadata=(("floor_applied", str(floor_applied)),),
    )


def aggregate_inter_bucket(
    bucket_capitals: tuple[SaCvaBucketCapital, ...],
    *,
    config: SaCvaAggregationConfig,
    m_cva: float = M_CVA_DEFAULT,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Aggregate bucket capitals to risk-class capital.

    Parameters
    ----------
    bucket_capitals : tuple[SaCvaBucketCapital, ...]
        Bucket-level ``K_b`` capitals prior to risk-class aggregation.
    config : SaCvaAggregationConfig
        Risk-class aggregation hooks (intra-bucket correlation, inter-bucket gamma,
        citation ids).
    m_cva : float, optional
        SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).
    profile : CvaRegulatoryProfile | str, optional
        Regulatory profile label or enum value; defaults to Basel MAR50 (2020).

    Returns
    -------
    SaCvaRiskClassCapital
        Risk-class capital with pre- and post-multiplier totals and bucket breakdown.
    """

    if not bucket_capitals:
        raise CvaInputError("risk class requires at least one bucket", field="bucket_capitals")

    validated_m_cva = validate_m_cva_multiplier(m_cva)
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
    cross_term = 0.0
    gamma_citations: list[str] = []
    for left_index, left_bucket in enumerate(bucket_capitals):
        for right_index, right_bucket in enumerate(bucket_capitals):
            if left_index == right_index:
                continue
            gamma_bc, gamma_citation = config.inter_bucket_gamma(
                left_bucket.bucket_id,
                right_bucket.bucket_id,
            )
            if gamma_citation not in gamma_citations:
                gamma_citations.append(gamma_citation)
            cross_term += gamma_bc * bucket_sb[left_index] * bucket_sb[right_index]
    pre_multiplier = math.sqrt(max(sum_kb_squared + cross_term, 0.0))
    post_multiplier = validated_m_cva * pre_multiplier
    citations = profile_citation_ids(
        (*tuple(gamma_citations), "basel_mar50_53"),
        profile,
    )
    return SaCvaRiskClassCapital(
        risk_class=config.risk_class,
        risk_measure=config.risk_measure,
        pre_multiplier_capital=pre_multiplier,
        post_multiplier_capital=post_multiplier,
        m_cva=validated_m_cva,
        bucket_capitals=bucket_capitals,
        citations=citations,
    )


def aggregate_weighted_sensitivities(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
    *,
    config: SaCvaAggregationConfig,
    m_cva: float = M_CVA_DEFAULT,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Group weighted sensitivities by bucket and aggregate to risk-class capital.

    Parameters
    ----------
    weighted_sensitivities : tuple[SaCvaWeightedSensitivity, ...]
        Net and hedge-weighted SA-CVA sensitivities validated for bucket aggregation.
    config : SaCvaAggregationConfig
        Risk-class aggregation hooks (intra-bucket correlation, inter-bucket gamma,
        citation ids).
    m_cva : float, optional
        SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).
    profile : CvaRegulatoryProfile | str, optional
        Regulatory profile label or enum value; defaults to Basel MAR50 (2020).

    Returns
    -------
    SaCvaRiskClassCapital
        Risk-class capital after intra- and inter-bucket MAR50.53 aggregation.
    """

    buckets: dict[str, list[SaCvaWeightedSensitivity]] = defaultdict(list)
    for item in weighted_sensitivities:
        buckets[item.risk_factor_key.bucket_id].append(item)
    bucket_capitals = tuple(
        aggregate_intra_bucket(
            bucket_id,
            tuple(sorted(items, key=lambda entry: entry.risk_factor_key.risk_factor_key)),
            config=config,
            profile=profile,
        )
        for bucket_id, items in sorted(buckets.items())
    )
    return aggregate_inter_bucket(
        bucket_capitals,
        config=config,
        m_cva=m_cva,
        profile=profile,
    )


def uniform_inter_bucket_gamma(gamma_bc: float, citation_id: str) -> InterBucketGammaFn:
    """Build a uniform inter-bucket gamma lookup for SA-CVA aggregation.

    Parameters
    ----------
    gamma_bc : float
        Inter-bucket correlation ``gamma_bc`` applied uniformly to all bucket pairs.
    citation_id : str
        Profile-specific citation id attached to the gamma for audit replay.

    Returns
    -------
    InterBucketGammaFn
        Callable ``(left_bucket, right_bucket) -> (gamma_bc, citation_id)`` that
        ignores bucket ids and returns the fixed pair.
    """

    def _lookup(left_bucket: str, right_bucket: str) -> tuple[float, str]:
        del left_bucket, right_bucket
        return gamma_bc, citation_id

    return _lookup


def _girr_delta_intra_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    left_tenor = left.risk_factor_key.tenor
    right_tenor = right.risk_factor_key.tenor
    if left_tenor is None or right_tenor is None:
        raise CvaInputError(
            "GIRR delta intra-bucket aggregation requires tenor",
            field="tenor",
        )
    return girr_delta_intra_bucket_correlation(left_tenor, right_tenor, profile=profile)


def _girr_vega_intra_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    return girr_vega_intra_bucket_correlation(
        left.risk_factor_key.risk_factor_key,
        right.risk_factor_key.risk_factor_key,
        profile=profile,
    )


def girr_delta_aggregation_config(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaAggregationConfig:
    """Return cited GIRR delta aggregation configuration.

    Parameters
    ----------
    profile : CvaRegulatoryProfile | str, optional
        Regulatory profile label or enum value; defaults to Basel MAR50 (2020).

    Returns
    -------
    SaCvaAggregationConfig
        GIRR delta hooks with profile-mapped intra-bucket rho and inter-bucket gamma.
    """

    def _intra(
        left: SaCvaWeightedSensitivity, right: SaCvaWeightedSensitivity
    ) -> tuple[float, str]:
        return _girr_delta_intra_correlation(left, right, profile=profile)

    gamma_bc, gamma_citation = girr_inter_bucket_correlation(profile=profile)

    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        intra_bucket_correlation=_intra,
        inter_bucket_gamma=uniform_inter_bucket_gamma(gamma_bc, gamma_citation),
        intra_bucket_citations=(
            profile_citation_id("basel_mar50_53", profile),
            profile_citation_id("basel_mar50_56", profile),
        ),
    )


def girr_vega_aggregation_config(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaAggregationConfig:
    """Return cited GIRR vega aggregation configuration.

    Parameters
    ----------
    profile : CvaRegulatoryProfile | str, optional
        Regulatory profile label or enum value; defaults to Basel MAR50 (2020).

    Returns
    -------
    SaCvaAggregationConfig
        GIRR vega hooks with profile-mapped intra-bucket rho and inter-bucket gamma.
    """

    def _intra(
        left: SaCvaWeightedSensitivity, right: SaCvaWeightedSensitivity
    ) -> tuple[float, str]:
        return _girr_vega_intra_correlation(left, right, profile=profile)

    gamma_bc, gamma_citation = girr_inter_bucket_correlation(profile=profile)
    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        intra_bucket_correlation=_intra,
        inter_bucket_gamma=uniform_inter_bucket_gamma(gamma_bc, gamma_citation),
        intra_bucket_citations=(
            profile_citation_id("basel_mar50_53", profile),
            profile_citation_id("basel_mar50_58", profile),
        ),
    )


__all__ = [
    "HEDGING_DISALLOWANCE_R",
    "M_CVA_DEFAULT",
    "InterBucketGammaFn",
    "IntraBucketCorrelationFn",
    "SaCvaAggregationConfig",
    "aggregate_inter_bucket",
    "aggregate_intra_bucket",
    "aggregate_weighted_sensitivities",
    "girr_delta_aggregation_config",
    "girr_vega_aggregation_config",
    "uniform_inter_bucket_gamma",
]
