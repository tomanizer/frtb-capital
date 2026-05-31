from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskFactorKey,
    SaCvaRiskMeasure,
    SaCvaWeightedSensitivity,
)
from frtb_cva.aggregation import (
    HEDGING_DISALLOWANCE_R,
    aggregate_intra_bucket,
    aggregate_weighted_sensitivities,
)


def _weighted(
    net: float,
    *,
    bucket: str = "USD",
    factor: str = "5y",
    hedge: float = 0.0,
) -> SaCvaWeightedSensitivity:
    key = SaCvaRiskFactorKey(
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        bucket_id=bucket,
        risk_factor_key=factor,
        tenor=factor,
    )
    risk_weight = 0.0074
    weighted_cva = net * risk_weight
    weighted_hedge = hedge * risk_weight
    return SaCvaWeightedSensitivity(
        risk_factor_key=key,
        gross_cva_amount=net,
        gross_hedge_amount=hedge,
        net_amount=net + hedge,
        risk_weight=risk_weight,
        weighted_cva=weighted_cva,
        weighted_hedge=weighted_hedge,
        weighted_net=weighted_cva + weighted_hedge,
        source_sensitivity_ids=(),
        citations=("basel_mar50_56",),
    )


def test_intra_bucket_reconciles_to_weighted_inputs() -> None:
    bucket = aggregate_intra_bucket("USD", (_weighted(1_000_000.0),))
    assert bucket.k_b == pytest.approx(1_000_000.0 * 0.0074)
    assert bucket.s_b == pytest.approx(1_000_000.0 * 0.0074)


def test_hedging_disallowance_constant_is_cited() -> None:
    assert HEDGING_DISALLOWANCE_R == pytest.approx(0.01)


def test_hedging_disallowance_adds_non_negative_penalty_for_offsetting_hedge() -> None:
    """MAR50.55: R · Σ (WS^HDG)² must not reduce K_b when CVA and hedge offset."""
    hedge_amount = -1_000_000.0
    item = _weighted(1_000_000.0, hedge=hedge_amount)
    bucket = aggregate_intra_bucket("USD", (item,))
    weighted_hedge = hedge_amount * item.risk_weight
    expected = math.sqrt(HEDGING_DISALLOWANCE_R * weighted_hedge * weighted_hedge)
    assert item.weighted_net == pytest.approx(0.0)
    assert bucket.k_b == pytest.approx(expected)
    assert bucket.k_b > 0.0


def test_inter_bucket_aggregation_produces_risk_class_total() -> None:
    risk_class = aggregate_weighted_sensitivities(
        (
            _weighted(1_000_000.0, bucket="USD", factor="5y"),
            _weighted(500_000.0, bucket="EUR", factor="5y"),
        )
    )
    assert risk_class.post_multiplier_capital > 0.0
    assert len(risk_class.bucket_capitals) == 2
