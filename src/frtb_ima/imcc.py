"""
Internal Model Capital Charge (IMCC) prototype.

Working assumptions (NPR 2.0 / Basel FRTB IMA):

    IMCC = 0.5 * IMCC_unconstrained + 0.5 * IMCC_constrained

    IMCC_unconstrained: LHA ES computed across all risk classes simultaneously.

    IMCC_constrained: sum of per-risk-class LHA ES values (no cross-class
                      diversification credit).

The stress period is applied via a scaling ratio on a reduced-scenario set:

    scaled_stress_ES = stress_reduced_ES * max(current_full_ES / current_reduced_ES, 1.0)

This ensures the stress ES is never deflated by the reduced set.
"""

from __future__ import annotations

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.liquidity_horizon import lha_es_from_vectors


def imcc_unconstrained(
    all_risk_class_vectors: dict[LiquidityHorizon, list[float]],
    alpha: float = 0.975,
) -> float:
    """
    Compute unconstrained IMCC as the LHA ES of all-risk-class aggregated vectors.

    Args:
        all_risk_class_vectors: Nested LH vectors with all risk classes aggregated
                                into each sub-vector.
        alpha: ES confidence level.

    Returns:
        Unconstrained IMCC scalar.
    """
    return lha_es_from_vectors(all_risk_class_vectors, alpha=alpha)


def imcc_constrained(
    per_risk_class_vectors: dict[RiskClass, dict[LiquidityHorizon, list[float]]],
    alpha: float = 0.975,
) -> float:
    """
    Compute constrained IMCC as the sum of per-risk-class LHA ES values.

    No diversification credit across risk classes.

    Args:
        per_risk_class_vectors: Nested LH vectors keyed by RiskClass then
                                LiquidityHorizon.
        alpha: ES confidence level.

    Returns:
        Constrained IMCC scalar.
    """
    total = 0.0
    for rc, lh_vectors in per_risk_class_vectors.items():
        if LiquidityHorizon.LH10 not in lh_vectors:
            raise KeyError(
                f"RiskClass {rc} is missing the LH10 vector required for LHA ES"
            )
        total += lha_es_from_vectors(lh_vectors, alpha=alpha)
    return total


def imcc(
    all_risk_class_vectors: dict[LiquidityHorizon, list[float]],
    per_risk_class_vectors: dict[RiskClass, dict[LiquidityHorizon, list[float]]],
    alpha: float = 0.975,
    w: float = 0.5,
) -> float:
    """
    Compute final IMCC = w * unconstrained + (1 - w) * constrained.

    Default w = 0.5 per NPR 2.0 working assumption.

    Args:
        all_risk_class_vectors: All-class aggregated LH vectors for unconstrained.
        per_risk_class_vectors: Per-class LH vectors for constrained.
        alpha: ES confidence level.
        w:     Weight on unconstrained component.

    Returns:
        IMCC scalar.
    """
    u = imcc_unconstrained(all_risk_class_vectors, alpha=alpha)
    c = imcc_constrained(per_risk_class_vectors, alpha=alpha)
    return w * u + (1.0 - w) * c


def scale_stress_es(
    stress_reduced_es: float,
    current_full_es: float,
    current_reduced_es: float,
) -> float:
    """
    Scale stress-period ES from a reduced risk-factor set to the full set.

    Per NPR 2.0 / Basel FRTB IMA indirect approach:

        scaled_stress_ES = stress_reduced_ES * max(current_full_ES / current_reduced_ES, 1.0)

    The floor of 1.0 on the ratio ensures we never deflate the stress ES.

    Args:
        stress_reduced_es:  ES computed over the stress period using the
                            reduced (75-factor) risk-factor set.
        current_full_es:    ES over the current period using all risk factors.
        current_reduced_es: ES over the current period using the reduced set.

    Returns:
        Scaled stress ES.

    Raises:
        ValueError: if current_reduced_es is zero (division undefined).
    """
    if current_reduced_es == 0.0:
        raise ValueError(
            "current_reduced_es is zero — cannot compute scaling ratio"
        )
    ratio = max(current_full_es / current_reduced_es, 1.0)
    return stress_reduced_es * ratio
