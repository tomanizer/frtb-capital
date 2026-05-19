"""
Liquidity horizon adjustment (LHA) for expected shortfall.

Per NPR 2.0 / Basel FRTB IMA, the LHA ES is computed from nested
P&L vectors — one per liquidity-horizon subset — NOT by scaling a
single scalar ES by sqrt(weighted_avg_LH / 10).

Formula (working assumption):

    LHA_ES = sqrt(
        ES(P_all)^2
        + ((20 - 10) / 10)  * ES(P_LH20plus)^2
        + ((40 - 20) / 10)  * ES(P_LH40plus)^2
        + ((60 - 40) / 10)  * ES(P_LH60plus)^2
        + ((120 - 60) / 10) * ES(P_LH120plus)^2
    )

Where:
    P_all       = all risk factors (LH >= 10)
    P_LH20plus  = risk factors with LH >= 20
    P_LH40plus  = risk factors with LH >= 40
    P_LH60plus  = risk factors with LH >= 60
    P_LH120plus = risk factors with LH >= 120

Each sub-vector is the aggregated P&L from the relevant subset of
risk factors over a common 10-day scenario horizon.

The nested structure means the sub-vectors are NOT independent draws —
they are constructed from the same historical scenario windows but
restricted to the relevant risk-factor subset.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.expected_shortfall import expected_shortfall

# (lh_cutoff, weight_numerator, weight_denominator)
# weight = (lh_upper - lh_lower) / base_horizon
# base_horizon = 10 business days
_LHA_STEPS: list[tuple[LiquidityHorizon, float]] = [
    (LiquidityHorizon.LH10,  1.0),   # ES(P_all): weight = (10-10)/10 + 1 ... just the base term
    (LiquidityHorizon.LH20,  (20 - 10) / 10),
    (LiquidityHorizon.LH40,  (40 - 20) / 10),
    (LiquidityHorizon.LH60,  (60 - 40) / 10),
    (LiquidityHorizon.LH120, (120 - 60) / 10),
]


def lha_es_from_vectors(
    lh_vectors: dict[LiquidityHorizon, Sequence[float]],
    alpha: float = 0.975,
) -> float:
    """
    Compute liquidity-horizon-adjusted ES from nested scenario vectors.

    Args:
        lh_vectors: Mapping from LiquidityHorizon cutoff to the P&L vector
                    for risk factors at or above that horizon.
                    Must contain at least LH10 (the full set).
        alpha:      ES confidence level.

    Returns:
        LHA ES scalar (positive = loss).

    Raises:
        KeyError:   if LH10 vector is missing.
        ValueError: if any vector is empty.
    """
    if LiquidityHorizon.LH10 not in lh_vectors:
        raise KeyError("lh_vectors must contain LH10 (the full risk-factor vector)")

    sum_sq = 0.0
    for lh, weight in _LHA_STEPS:
        if lh not in lh_vectors:
            # Missing sub-vector: no risk factors at this horizon or above.
            # Contribution is zero — a valid outcome for a simple desk.
            continue
        es = expected_shortfall(list(lh_vectors[lh]), alpha=alpha)
        sum_sq += weight * es ** 2

    return math.sqrt(sum_sq)


def lha_es_from_scalars(
    es_by_lh: dict[LiquidityHorizon, float],
) -> float:
    """
    Compute LHA ES directly from pre-computed ES scalars per LH subset.

    Convenience wrapper for callers that have already computed ES per subset.
    Same formula as lha_es_from_vectors.

    Args:
        es_by_lh: Mapping from LiquidityHorizon cutoff to pre-computed ES.
                  Must contain at least LH10.

    Returns:
        LHA ES scalar.
    """
    if LiquidityHorizon.LH10 not in es_by_lh:
        raise KeyError("es_by_lh must contain LH10 (the full risk-factor ES)")

    sum_sq = 0.0
    for lh, weight in _LHA_STEPS:
        es = es_by_lh.get(lh, 0.0)
        sum_sq += weight * es ** 2

    return math.sqrt(sum_sq)


# ---------------------------------------------------------------------------
# Toy approximation — clearly labelled, never used in the main path
# ---------------------------------------------------------------------------

def lha_es_scalar_approximation(
    es_full: float,
    weighted_avg_lh_days: float,
    base_horizon_days: float = 10.0,
) -> float:
    """
    Scalar approximation: ES_full * sqrt(weighted_avg_LH / base_horizon).

    WARNING: This is a simplified toy approximation.
    It is provided only for comparison / educational purposes.
    Do NOT use this as the primary LHA calculation.
    The nested-vector method (lha_es_from_vectors) is the required approach.
    """
    return es_full * math.sqrt(weighted_avg_lh_days / base_horizon_days)
