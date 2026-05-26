"""Tests for building nested LH vectors from scenario cubes."""

from datetime import date

import numpy as np
import pytest

from frtb_ima.data_contracts import RiskFactorDefinition, ScenarioCube
from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.lha_builder import (
    imcc_nested_lh_vectors_from_cube,
    nested_lh_vectors_from_cube,
    per_risk_class_nested_lh_vectors_from_cube,
    risk_factor_names_for_lh_subset,
)
from frtb_ima.scenario import ScenarioSetType, make_scenario_metadata


def _risk_factors() -> tuple[RiskFactorDefinition, ...]:
    return (
        RiskFactorDefinition(
            name="USD_RATE",
            risk_class=RiskClass.GIRR,
            liquidity_horizon=LiquidityHorizon.LH10,
        ),
        RiskFactorDefinition(
            name="EUR_RATE",
            risk_class=RiskClass.GIRR,
            liquidity_horizon=LiquidityHorizon.LH20,
        ),
        RiskFactorDefinition(
            name="IG_CREDIT",
            risk_class=RiskClass.CSR,
            liquidity_horizon=LiquidityHorizon.LH40,
        ),
    )


def _cube() -> ScenarioCube:
    metadata = make_scenario_metadata(
        [date(2025, 1, 1), date(2025, 1, 2)],
        scenario_set=ScenarioSetType.CURRENT,
    )
    # shape: scenario x position x risk_factor
    values = np.array(
        [
            [[1.0, 10.0, 100.0], [2.0, 20.0, 200.0]],
            [[3.0, 30.0, 300.0], [4.0, 40.0, 400.0]],
        ]
    )
    return ScenarioCube(
        values=values,
        scenario_metadata=metadata,
        position_ids=("P1", "P2"),
        risk_factor_names=("USD_RATE", "EUR_RATE", "IG_CREDIT"),
    )


def test_risk_factor_names_for_lh_subset() -> None:
    risk_factors = _risk_factors()

    assert risk_factor_names_for_lh_subset(
        risk_factors,
        LiquidityHorizon.LH10,
    ) == ("USD_RATE", "EUR_RATE", "IG_CREDIT")
    assert risk_factor_names_for_lh_subset(
        risk_factors,
        LiquidityHorizon.LH20,
    ) == ("EUR_RATE", "IG_CREDIT")
    assert risk_factor_names_for_lh_subset(
        risk_factors,
        LiquidityHorizon.LH40,
        risk_class=RiskClass.CSR,
    ) == ("IG_CREDIT",)


def test_nested_lh_vectors_from_cube_all_classes() -> None:
    result = nested_lh_vectors_from_cube(_cube(), _risk_factors())

    assert result[LiquidityHorizon.LH10].values.tolist() == pytest.approx([333.0, 777.0])
    assert result[LiquidityHorizon.LH20].values.tolist() == pytest.approx([330.0, 770.0])
    assert result[LiquidityHorizon.LH40].values.tolist() == pytest.approx([300.0, 700.0])
    assert LiquidityHorizon.LH60 not in result
    assert result[LiquidityHorizon.LH10].metadata == _cube().scenario_metadata


def test_nested_lh_vectors_from_cube_for_one_risk_class() -> None:
    result = nested_lh_vectors_from_cube(
        _cube(),
        _risk_factors(),
        risk_class=RiskClass.GIRR,
    )

    assert result[LiquidityHorizon.LH10].values.tolist() == pytest.approx([33.0, 77.0])
    assert result[LiquidityHorizon.LH20].values.tolist() == pytest.approx([30.0, 70.0])
    assert LiquidityHorizon.LH40 not in result


def test_per_risk_class_nested_lh_vectors_from_cube() -> None:
    result = per_risk_class_nested_lh_vectors_from_cube(_cube(), _risk_factors())

    assert set(result) == {RiskClass.GIRR, RiskClass.CSR}
    assert result[RiskClass.CSR][LiquidityHorizon.LH10].values.tolist() == pytest.approx(
        [300.0, 700.0]
    )
    assert result[RiskClass.CSR][LiquidityHorizon.LH40].values.tolist() == pytest.approx(
        [300.0, 700.0]
    )


def test_imcc_nested_lh_vectors_from_cube_returns_both_views() -> None:
    result = imcc_nested_lh_vectors_from_cube(_cube(), _risk_factors())

    assert result.all_risk_class_vectors[LiquidityHorizon.LH10].values.tolist() == (
        pytest.approx([333.0, 777.0])
    )
    assert RiskClass.GIRR in result.per_risk_class_vectors
    assert RiskClass.CSR in result.per_risk_class_vectors


def test_nested_lh_vectors_from_cube_rejects_missing_factor_definitions() -> None:
    with pytest.raises(KeyError, match="without definitions"):
        nested_lh_vectors_from_cube(_cube(), _risk_factors()[:-1])


def test_nested_lh_vectors_from_cube_rejects_duplicate_factor_definitions() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        nested_lh_vectors_from_cube(_cube(), (*_risk_factors(), _risk_factors()[0]))
