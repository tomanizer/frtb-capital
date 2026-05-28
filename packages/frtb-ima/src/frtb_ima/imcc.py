"""
Internal Model Capital Charge (IMCC).

Formula mechanics for the NPR 2.0 / Basel FRTB IMA policy profile:

    IMCC = 0.5 * IMCC_unconstrained + 0.5 * IMCC_constrained

    IMCC_unconstrained: LHA ES computed across all risk classes simultaneously.

    IMCC_constrained: sum of per-risk-class LHA ES values (no cross-class
                      diversification credit).

The stress period is applied via a scaling ratio on a reduced-scenario set:

    scaled_stress_ES = stress_reduced_ES * max(current_full_ES / current_reduced_ES, 1.0)

This ensures the stress ES is never deflated by the reduced set.

Regulatory traceability:
    Basel MAR33 IMA capital calculation; U.S. NPR 2.0 models-based non-default
    capital and reduced/full set stress scaling; EU CRR Articles 325ba, 325bb,
    and 325bc. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.liquidity_horizon import LHAESResult, lha_es_breakdown_from_vectors
from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import DEFAULT_LHA_WEIGHTS, RegulatoryPolicy
from frtb_ima.scenario import ScenarioVector

LHVectorInput: TypeAlias = Mapping[LiquidityHorizon, ScenarioVector | Sequence[float]]
PerRiskClassLHVectorInput: TypeAlias = Mapping[RiskClass, LHVectorInput]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IMCCRiskClassComponent:
    """One constrained IMCC component for a single regulatory risk class."""

    risk_class: RiskClass
    lha_es_result: LHAESResult

    @property
    def lha_es(self) -> float:
        """Risk-class LHA ES contribution to constrained IMCC."""
        return self.lha_es_result.lha_es

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_class": self.risk_class.value,
            "lha_es": self.lha_es,
            "lha_es_result": self.lha_es_result.as_dict(),
        }


@dataclass(frozen=True)
class IMCCResult:
    """Audit-friendly decomposition of the IMCC blend."""

    alpha: float
    estimator: ESEstimator
    unconstrained_weight: float
    unconstrained: LHAESResult
    constrained_components: tuple[IMCCRiskClassComponent, ...]
    constrained_lha_es: float
    imcc: float

    @property
    def constrained_weight(self) -> float:
        """Weight applied to the constrained component."""
        return 1.0 - self.unconstrained_weight

    @property
    def unconstrained_lha_es(self) -> float:
        """All-risk-class LHA ES used in the unconstrained component."""
        return self.unconstrained.lha_es

    def component_by_risk_class(
        self,
        risk_class: RiskClass,
    ) -> IMCCRiskClassComponent:
        """Return the constrained component for one risk class."""
        for component in self.constrained_components:
            if component.risk_class == risk_class:
                return component
        raise KeyError(f"No IMCC constrained component for risk class {risk_class.value}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "alpha": self.alpha,
            "estimator": self.estimator.value,
            "unconstrained_weight": self.unconstrained_weight,
            "constrained_weight": self.constrained_weight,
            "unconstrained_lha_es": self.unconstrained_lha_es,
            "constrained_lha_es": self.constrained_lha_es,
            "imcc": self.imcc,
            "unconstrained": self.unconstrained.as_dict(),
            "constrained_components": [
                component.as_dict() for component in self.constrained_components
            ],
        }

    def summary_lines(self) -> list[str]:
        """Return a compact text summary suitable for logs or examples."""
        lines = [
            f"IMCC alpha={self.alpha:.4f} estimator={self.estimator.value}",
            f"unconstrained_weight={self.unconstrained_weight:.6f}",
            f"unconstrained_lha_es={self.unconstrained_lha_es:.6f}",
            f"constrained_weight={self.constrained_weight:.6f}",
            f"constrained_lha_es={self.constrained_lha_es:.6f}",
            f"imcc={self.imcc:.6f}",
        ]
        for component in self.constrained_components:
            lines.append(f"{component.risk_class.value} constrained_lha_es={component.lha_es:.6f}")
        return lines


@dataclass(frozen=True)
class StressScalingResult:
    """Audit-friendly reduced-set stress ES scaling result."""

    stress_reduced_es: float
    current_full_es: float
    current_reduced_es: float
    raw_ratio: float
    applied_ratio: float
    floor_applied: bool
    scaled_stress_es: float

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "stress_reduced_es": self.stress_reduced_es,
            "current_full_es": self.current_full_es,
            "current_reduced_es": self.current_reduced_es,
            "raw_ratio": self.raw_ratio,
            "applied_ratio": self.applied_ratio,
            "floor_applied": self.floor_applied,
            "scaled_stress_es": self.scaled_stress_es,
        }

    def summary_lines(self) -> list[str]:
        """Return a compact text summary suitable for logs or examples."""
        return [
            f"stress_reduced_es={self.stress_reduced_es:.6f}",
            f"current_full_es={self.current_full_es:.6f}",
            f"current_reduced_es={self.current_reduced_es:.6f}",
            f"raw_ratio={self.raw_ratio:.6f}",
            f"applied_ratio={self.applied_ratio:.6f}",
            f"floor_applied={self.floor_applied}",
            f"scaled_stress_es={self.scaled_stress_es:.6f}",
        ]


def _validate_non_negative_finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative, got {value}")


def imcc_unconstrained(
    all_risk_class_vectors: LHVectorInput,
    alpha: float,
    estimator: ESEstimator,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> float:
    """
    Compute unconstrained IMCC as the LHA ES of all-risk-class aggregated vectors.

    Args:
        all_risk_class_vectors: Nested LH vectors with all risk classes aggregated
                                into each sub-vector.
        alpha: ES confidence level.
        lha_weights: Liquidity-horizon weights by nested vector.

    Returns:
        Unconstrained IMCC scalar.
    """
    return imcc_unconstrained_breakdown(
        all_risk_class_vectors,
        alpha=alpha,
        estimator=estimator,
        lha_weights=lha_weights,
    ).lha_es


def imcc_unconstrained_breakdown(
    all_risk_class_vectors: LHVectorInput,
    alpha: float,
    estimator: ESEstimator,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> LHAESResult:
    """Compute the unconstrained all-risk-class LHA ES decomposition."""
    return lha_es_breakdown_from_vectors(
        all_risk_class_vectors,
        alpha=alpha,
        estimator=estimator,
        lha_weights=lha_weights,
    )


def imcc_constrained(
    per_risk_class_vectors: PerRiskClassLHVectorInput,
    alpha: float,
    estimator: ESEstimator,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> float:
    """
    Compute constrained IMCC as the sum of per-risk-class LHA ES values.

    No diversification credit across risk classes.

    Args:
        per_risk_class_vectors: Nested LH vectors keyed by RiskClass then
                                LiquidityHorizon.
        alpha: ES confidence level.
        lha_weights: Liquidity-horizon weights by nested vector.

    Returns:
        Constrained IMCC scalar.
    """
    return sum(
        component.lha_es
        for component in imcc_constrained_breakdown(
            per_risk_class_vectors,
            alpha=alpha,
            estimator=estimator,
            lha_weights=lha_weights,
        )
    )


def imcc_constrained_breakdown(
    per_risk_class_vectors: PerRiskClassLHVectorInput,
    alpha: float,
    estimator: ESEstimator,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> tuple[IMCCRiskClassComponent, ...]:
    """Compute per-risk-class constrained LHA ES components."""
    components: list[IMCCRiskClassComponent] = []
    for risk_class in sorted(per_risk_class_vectors, key=lambda item: item.value):
        lh_vectors = per_risk_class_vectors[risk_class]
        if LiquidityHorizon.LH10 not in lh_vectors:
            raise KeyError(f"RiskClass {risk_class} is missing the LH10 vector required for LHA ES")
        components.append(
            IMCCRiskClassComponent(
                risk_class=risk_class,
                lha_es_result=lha_es_breakdown_from_vectors(
                    lh_vectors,
                    alpha=alpha,
                    estimator=estimator,
                    lha_weights=lha_weights,
                ),
            )
        )
    return tuple(components)


def imcc(
    all_risk_class_vectors: LHVectorInput,
    per_risk_class_vectors: PerRiskClassLHVectorInput,
    alpha: float,
    estimator: ESEstimator,
    w: float,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> float:
    """
    Compute final IMCC = w * unconstrained + (1 - w) * constrained.

    ``w`` must be supplied by the caller or sourced from ``RegulatoryPolicy``.

    Args:
        all_risk_class_vectors: All-class aggregated LH vectors for unconstrained.
        per_risk_class_vectors: Per-class LH vectors for constrained.
        alpha: ES confidence level.
        w:     Weight on unconstrained component.
        lha_weights: Liquidity-horizon weights by nested vector.

    Returns:
        IMCC scalar.
    """
    return imcc_breakdown(
        all_risk_class_vectors,
        per_risk_class_vectors,
        alpha=alpha,
        estimator=estimator,
        w=w,
        lha_weights=lha_weights,
    ).imcc


def imcc_breakdown(
    all_risk_class_vectors: LHVectorInput,
    per_risk_class_vectors: PerRiskClassLHVectorInput,
    alpha: float,
    estimator: ESEstimator,
    w: float,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> IMCCResult:
    """
    Compute final IMCC and return the constrained/unconstrained decomposition.

    The scalar formula remains:

        IMCC = w * unconstrained_LHA_ES + (1 - w) * constrained_LHA_ES
    """
    if not math.isfinite(w) or not (0.0 <= w <= 1.0):
        raise ValueError(f"w must be finite and in [0, 1], got {w}")

    unconstrained = imcc_unconstrained_breakdown(
        all_risk_class_vectors,
        alpha=alpha,
        estimator=estimator,
        lha_weights=lha_weights,
    )
    constrained_components = imcc_constrained_breakdown(
        per_risk_class_vectors,
        alpha=alpha,
        estimator=estimator,
        lha_weights=lha_weights,
    )
    constrained_lha_es = sum(component.lha_es for component in constrained_components)
    imcc_value = w * unconstrained.lha_es + (1.0 - w) * constrained_lha_es
    return IMCCResult(
        alpha=alpha,
        estimator=estimator,
        unconstrained_weight=w,
        unconstrained=unconstrained,
        constrained_components=constrained_components,
        constrained_lha_es=constrained_lha_es,
        imcc=imcc_value,
    )


def imcc_for_policy(
    all_risk_class_vectors: LHVectorInput,
    per_risk_class_vectors: PerRiskClassLHVectorInput,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> float:
    """Compute IMCC using ES confidence level, LHA weights, and blend from policy."""
    result = imcc_breakdown(
        all_risk_class_vectors,
        per_risk_class_vectors,
        alpha=policy.es_confidence_level,
        estimator=policy.es_estimator,
        w=policy.imcc_unconstrained_weight,
        lha_weights=policy.lha_weights,
    )
    _log_imcc_result(result, policy, run_id=run_id, desk_id=desk_id)
    return result.imcc


def imcc_breakdown_for_policy(
    all_risk_class_vectors: LHVectorInput,
    per_risk_class_vectors: PerRiskClassLHVectorInput,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> IMCCResult:
    """Compute decomposed IMCC using ES confidence, LHA weights, and blend policy."""
    result = imcc_breakdown(
        all_risk_class_vectors,
        per_risk_class_vectors,
        alpha=policy.es_confidence_level,
        estimator=policy.es_estimator,
        w=policy.imcc_unconstrained_weight,
        lha_weights=policy.lha_weights,
    )
    _log_imcc_result(result, policy, run_id=run_id, desk_id=desk_id)
    return result


def _log_imcc_result(
    result: IMCCResult,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None,
    desk_id: str | None,
) -> None:
    logger.info(
        "imcc_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            imcc=result.imcc,
            unconstrained_lha_es=result.unconstrained_lha_es,
            constrained_lha_es=result.constrained_lha_es,
            constrained_component_count=len(result.constrained_components),
        ),
    )


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
    return scale_stress_es_breakdown(
        stress_reduced_es,
        current_full_es,
        current_reduced_es,
    ).scaled_stress_es


def scale_stress_es_breakdown(
    stress_reduced_es: float,
    current_full_es: float,
    current_reduced_es: float,
) -> StressScalingResult:
    """
    Scale stress-period ES and return the full reduced-set scaling audit trail.

    The applied ratio is floored at 1.0 so the reduced-set scaling step never
    deflates stress-period ES.
    """
    _validate_non_negative_finite(stress_reduced_es, "stress_reduced_es")
    _validate_non_negative_finite(current_full_es, "current_full_es")
    _validate_non_negative_finite(current_reduced_es, "current_reduced_es")

    if current_reduced_es == 0.0:
        raise ValueError("current_reduced_es is zero; cannot compute scaling ratio")
    raw_ratio = current_full_es / current_reduced_es
    applied_ratio = max(raw_ratio, 1.0)
    return StressScalingResult(
        stress_reduced_es=stress_reduced_es,
        current_full_es=current_full_es,
        current_reduced_es=current_reduced_es,
        raw_ratio=raw_ratio,
        applied_ratio=applied_ratio,
        floor_applied=raw_ratio < 1.0,
        scaled_stress_es=stress_reduced_es * applied_ratio,
    )
