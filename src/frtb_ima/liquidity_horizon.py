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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.expected_shortfall import expected_shortfall
from frtb_ima.scenario import ScenarioVector
from frtb_ima.scenario_validation import validate_nested_lh_vectors

# (lh_cutoff, weight)
# weight = (lh_upper - lh_lower) / base_horizon
# base_horizon = 10 business days
_LHA_STEPS: list[tuple[LiquidityHorizon, float]] = [
    (LiquidityHorizon.LH10, 1.0),
    (LiquidityHorizon.LH20, (20 - 10) / 10),
    (LiquidityHorizon.LH40, (40 - 20) / 10),
    (LiquidityHorizon.LH60, (60 - 40) / 10),
    (LiquidityHorizon.LH120, (120 - 60) / 10),
]


@dataclass(frozen=True)
class LHAESComponent:
    """One liquidity-horizon contribution to the LHA ES aggregation."""

    liquidity_horizon: LiquidityHorizon
    weight: float
    expected_shortfall: float
    weighted_square: float
    present: bool


@dataclass(frozen=True)
class LHAESResult:
    """Audit-friendly decomposition of a liquidity-horizon-adjusted ES result."""

    alpha: float
    components: tuple[LHAESComponent, ...]
    sum_weighted_squares: float
    lha_es: float
    scenario_count: int | None = None
    metadata_aligned: bool | None = None

    def component_by_horizon(self, lh: LiquidityHorizon) -> LHAESComponent:
        """Return the decomposition component for one liquidity horizon."""
        for component in self.components:
            if component.liquidity_horizon == lh:
                return component
        raise KeyError(f"No component for liquidity horizon {lh.name}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "alpha": self.alpha,
            "sum_weighted_squares": self.sum_weighted_squares,
            "lha_es": self.lha_es,
            "scenario_count": self.scenario_count,
            "metadata_aligned": self.metadata_aligned,
            "components": [
                {
                    "liquidity_horizon": component.liquidity_horizon.name,
                    "weight": component.weight,
                    "expected_shortfall": component.expected_shortfall,
                    "weighted_square": component.weighted_square,
                    "present": component.present,
                }
                for component in self.components
            ],
        }

    def summary_lines(self) -> list[str]:
        """Return a compact text summary suitable for logs or examples."""
        lines = [
            f"LHA ES alpha={self.alpha:.4f}",
            f"sum_weighted_squares={self.sum_weighted_squares:.6f}",
            f"lha_es={self.lha_es:.6f}",
        ]
        if self.scenario_count is not None:
            lines.append(f"scenario_count={self.scenario_count}")
        if self.metadata_aligned is not None:
            lines.append(f"metadata_aligned={self.metadata_aligned}")
        for component in self.components:
            lines.append(
                " ".join(
                    [
                        component.liquidity_horizon.name,
                        f"present={component.present}",
                        f"weight={component.weight:.6f}",
                        f"es={component.expected_shortfall:.6f}",
                        f"weighted_square={component.weighted_square:.6f}",
                    ]
                )
            )
        return lines


def _values_as_list(vector: ScenarioVector | Sequence[float]) -> list[float]:
    if isinstance(vector, ScenarioVector):
        return vector.tolist()
    return list(vector)


def lha_es_breakdown_from_vectors(
    lh_vectors: Mapping[LiquidityHorizon, ScenarioVector | Sequence[float]],
    alpha: float = 0.975,
) -> LHAESResult:
    """
    Compute LHA ES and return an audit-friendly decomposition.

    This is the canonical vector-based reporting path. It validates nested
    liquidity-horizon vector structure before calculation.
    """
    validation = validate_nested_lh_vectors(lh_vectors)

    sum_sq = 0.0
    components: list[LHAESComponent] = []
    for lh, weight in _LHA_STEPS:
        if lh not in lh_vectors:
            components.append(
                LHAESComponent(
                    liquidity_horizon=lh,
                    weight=weight,
                    expected_shortfall=0.0,
                    weighted_square=0.0,
                    present=False,
                )
            )
            continue
        es = expected_shortfall(_values_as_list(lh_vectors[lh]), alpha=alpha)
        weighted_square = weight * es**2
        sum_sq += weighted_square
        components.append(
            LHAESComponent(
                liquidity_horizon=lh,
                weight=weight,
                expected_shortfall=es,
                weighted_square=weighted_square,
                present=True,
            )
        )

    return LHAESResult(
        alpha=alpha,
        components=tuple(components),
        sum_weighted_squares=sum_sq,
        lha_es=math.sqrt(sum_sq),
        scenario_count=validation.scenario_count,
        metadata_aligned=validation.metadata_aligned,
    )


def lha_es_breakdown_from_scalars(
    es_by_lh: Mapping[LiquidityHorizon, float],
    alpha: float = 0.975,
) -> LHAESResult:
    """
    Compute LHA ES from pre-computed ES scalars and return decomposition.

    This path is useful when ES has already been calculated upstream, but it
    does not validate scenario alignment because no vectors are supplied.
    """
    if LiquidityHorizon.LH10 not in es_by_lh:
        raise KeyError("es_by_lh must contain LH10 (the full risk-factor ES)")

    sum_sq = 0.0
    components: list[LHAESComponent] = []
    for lh, weight in _LHA_STEPS:
        present = lh in es_by_lh
        es = float(es_by_lh.get(lh, 0.0))
        weighted_square = weight * es**2
        sum_sq += weighted_square
        components.append(
            LHAESComponent(
                liquidity_horizon=lh,
                weight=weight,
                expected_shortfall=es,
                weighted_square=weighted_square,
                present=present,
            )
        )

    return LHAESResult(
        alpha=alpha,
        components=tuple(components),
        sum_weighted_squares=sum_sq,
        lha_es=math.sqrt(sum_sq),
    )


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
        ValueError: if any vector is empty or structurally invalid.
    """
    if LiquidityHorizon.LH10 not in lh_vectors:
        raise KeyError("lh_vectors must contain LH10 (the full risk-factor vector)")
    return lha_es_breakdown_from_vectors(lh_vectors, alpha=alpha).lha_es


def lha_es_from_scalars(
    es_by_lh: dict[LiquidityHorizon, float],
) -> float:
    """
    Compute LHA ES directly from pre-computed ES scalars per LH subset.

    Convenience wrapper for callers that have already computed ES per subset.
    Same formula as lha_es_from_vectors.
    """
    return lha_es_breakdown_from_scalars(es_by_lh).lha_es


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
