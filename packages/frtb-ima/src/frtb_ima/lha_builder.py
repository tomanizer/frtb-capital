"""
Build nested liquidity-horizon scenario vectors from scenario cubes.

The calculators in ``liquidity_horizon.py`` and ``imcc.py`` deliberately consume
already-nested vectors. This module is the vectorized bridge from risk-engine
scenario cubes to those calculation inputs.

Regulatory traceability:
    Supports NPR-MR-LHA-001 and NPR-MR-IMCC-001 in
    docs/requirements/NPR_2_0_MARKET_RISK.yml.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from frtb_ima.data_contracts import RiskFactorDefinition, ScenarioCube
from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.regimes import DEFAULT_LHA_WEIGHTS
from frtb_ima.scenario import ScenarioVector


@dataclass(frozen=True)
class NestedLHScenarioVectors:
    """Scenario vectors ready for LHA ES and IMCC calculations."""

    all_risk_class_vectors: dict[LiquidityHorizon, ScenarioVector]
    per_risk_class_vectors: dict[RiskClass, dict[LiquidityHorizon, ScenarioVector]]


def _risk_factor_map(
    risk_factors: Sequence[RiskFactorDefinition],
) -> dict[str, RiskFactorDefinition]:
    mapping = {risk_factor.name: risk_factor for risk_factor in risk_factors}
    if len(mapping) != len(risk_factors):
        raise ValueError("risk_factors contains duplicate names")
    return mapping


def _validate_cube_risk_factors(
    cube: ScenarioCube,
    risk_factor_by_name: Mapping[str, RiskFactorDefinition],
) -> None:
    missing = [
        risk_factor_name
        for risk_factor_name in cube.risk_factor_names
        if risk_factor_name not in risk_factor_by_name
    ]
    if missing:
        raise KeyError(f"ScenarioCube has risk factors without definitions: {missing}")


def risk_factor_names_for_lh_subset(
    risk_factors: Sequence[RiskFactorDefinition],
    liquidity_horizon: LiquidityHorizon,
    risk_class: RiskClass | None = None,
) -> tuple[str, ...]:
    """Return risk-factor names whose LH is at least the requested LH cutoff.

    ``LH10`` therefore means all selected factors, while ``LH40`` means factors
    with 40-, 60-, or 120-day liquidity horizons.
    Parameters
    ----------
    risk_factors : Sequence[RiskFactorDefinition]
        Risk factors.
    liquidity_horizon : LiquidityHorizon
        Liquidity horizon.
    risk_class : RiskClass | None, optional
        Risk class.

    Returns
    -------
    tuple[str, ...]
        Result of the operation.
    """
    return tuple(
        risk_factor.name
        for risk_factor in risk_factors
        if risk_factor.liquidity_horizon.value >= liquidity_horizon.value
        and (risk_class is None or risk_factor.risk_class == risk_class)
    )


def nested_lh_vectors_from_cube(
    cube: ScenarioCube,
    risk_factors: Sequence[RiskFactorDefinition],
    *,
    risk_class: RiskClass | None = None,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> dict[LiquidityHorizon, ScenarioVector]:
    """Build nested LH vectors from a scenario cube.

    The returned dictionary is keyed by LH cutoff. Missing longer-horizon
    buckets are omitted, but LH10 must have at least one risk factor.
    Parameters
    ----------
    cube : ScenarioCube
        Cube.
    risk_factors : Sequence[RiskFactorDefinition]
        Risk factors.
    risk_class : RiskClass | None, optional
        Risk class.
    lha_weights : Sequence[tuple[LiquidityHorizon, float]], optional
        Lha weights.

    Returns
    -------
    dict[LiquidityHorizon, ScenarioVector]
        Result of the operation.
    """
    risk_factor_by_name = _risk_factor_map(risk_factors)
    _validate_cube_risk_factors(cube, risk_factor_by_name)

    cube_risk_factors = tuple(risk_factor_by_name[name] for name in cube.risk_factor_names)
    vectors: dict[LiquidityHorizon, ScenarioVector] = {}
    for liquidity_horizon, _weight in lha_weights:
        selected_names = risk_factor_names_for_lh_subset(
            cube_risk_factors,
            liquidity_horizon,
            risk_class=risk_class,
        )
        if not selected_names:
            continue
        vectors[liquidity_horizon] = ScenarioVector(
            values=cube.pnl_for_risk_factors(selected_names),
            metadata=cube.scenario_metadata,
            risk_class=risk_class,
            liquidity_horizon=liquidity_horizon,
            name=(
                f"{risk_class.value if risk_class is not None else 'ALL'}_{liquidity_horizon.name}"
            ),
        )

    if LiquidityHorizon.LH10 not in vectors:
        scope = f" for risk class {risk_class.value}" if risk_class is not None else ""
        raise ValueError(f"ScenarioCube has no LH10 risk factors{scope}")
    return vectors


def per_risk_class_nested_lh_vectors_from_cube(
    cube: ScenarioCube,
    risk_factors: Sequence[RiskFactorDefinition],
    *,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> dict[RiskClass, dict[LiquidityHorizon, ScenarioVector]]:
    """Build nested LH vectors separately for every risk class present.
    Parameters
    ----------
    cube : ScenarioCube
        Cube.
    risk_factors : Sequence[RiskFactorDefinition]
        Risk factors.
    lha_weights : Sequence[tuple[LiquidityHorizon, float]], optional
        Lha weights.

    Returns
    -------
    dict[RiskClass, dict[LiquidityHorizon, ScenarioVector]]
        Result of the operation.
    """
    risk_factor_by_name = _risk_factor_map(risk_factors)
    _validate_cube_risk_factors(cube, risk_factor_by_name)
    risk_classes = sorted(
        {risk_factor_by_name[name].risk_class for name in cube.risk_factor_names},
        key=lambda risk_class: risk_class.value,
    )
    return {
        risk_class: nested_lh_vectors_from_cube(
            cube,
            risk_factors,
            risk_class=risk_class,
            lha_weights=lha_weights,
        )
        for risk_class in risk_classes
    }


def imcc_nested_lh_vectors_from_cube(
    cube: ScenarioCube,
    risk_factors: Sequence[RiskFactorDefinition],
    *,
    lha_weights: Sequence[tuple[LiquidityHorizon, float]] = DEFAULT_LHA_WEIGHTS,
) -> NestedLHScenarioVectors:
    """Build all-class and per-risk-class nested LH vectors for IMCC.
    Parameters
    ----------
    cube : ScenarioCube
        Cube.
    risk_factors : Sequence[RiskFactorDefinition]
        Risk factors.
    lha_weights : Sequence[tuple[LiquidityHorizon, float]], optional
        Lha weights.

    Returns
    -------
    NestedLHScenarioVectors
        Result of the operation.
    """
    return NestedLHScenarioVectors(
        all_risk_class_vectors=nested_lh_vectors_from_cube(
            cube,
            risk_factors,
            lha_weights=lha_weights,
        ),
        per_risk_class_vectors=per_risk_class_nested_lh_vectors_from_cube(
            cube,
            risk_factors,
            lha_weights=lha_weights,
        ),
    )
