from __future__ import annotations

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


def _weighted(net: float, *, bucket: str = "USD", factor: str = "5y") -> SaCvaWeightedSensitivity:
    key = SaCvaRiskFactorKey(
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        bucket_id=bucket,
        risk_factor_key=factor,
        tenor=factor,
    )
    return SaCvaWeightedSensitivity(
        risk_factor_key=key,
        gross_cva_amount=net,
        gross_hedge_amount=0.0,
        net_amount=net,
        risk_weight=0.0074,
        weighted_cva=net * 0.0074,
        weighted_hedge=0.0,
        weighted_net=net * 0.0074,
        citations=("basel_mar50_56",),
    )


def test_intra_bucket_reconciles_to_weighted_inputs() -> None:
    bucket = aggregate_intra_bucket("USD", (_weighted(1_000_000.0),))
    assert bucket.k_b == pytest.approx(1_000_000.0 * 0.0074)
    assert bucket.s_b == pytest.approx(1_000_000.0 * 0.0074)


def test_hedging_disallowance_constant_is_cited() -> None:
    assert HEDGING_DISALLOWANCE_R == pytest.approx(0.01)


def test_inter_bucket_aggregation_produces_risk_class_total() -> None:
    risk_class = aggregate_weighted_sensitivities(
        (
            _weighted(1_000_000.0, bucket="USD", factor="5y"),
            _weighted(500_000.0, bucket="EUR", factor="5y"),
        )
    )
    assert risk_class.post_multiplier_capital > 0.0
    assert len(risk_class.bucket_capitals) == 2
