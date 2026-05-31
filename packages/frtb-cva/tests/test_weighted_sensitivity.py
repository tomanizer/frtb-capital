from __future__ import annotations

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.weighted_sensitivity import compute_weighted_sensitivities


def _sensitivity(
    *,
    sensitivity_id: str,
    tag: SensitivityTag,
    amount: float,
    tenor: str = "5y",
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=tag,
        bucket_id="USD",
        risk_factor_key=tenor,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-{sensitivity_id}",
    )


def test_girr_delta_weighted_sensitivity_preserves_gross_and_net() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(sensitivity_id="cva-1", tag=SensitivityTag.CVA, amount=1_000_000.0),
            _sensitivity(sensitivity_id="hdg-1", tag=SensitivityTag.HDG, amount=250_000.0),
        ),
        eligible_hedge_ids=frozenset({"hdg-1"}),
    )
    assert len(weighted) == 1
    line = weighted[0]
    assert line.gross_cva_amount == pytest.approx(1_000_000.0)
    assert line.gross_hedge_amount == pytest.approx(250_000.0)
    assert line.net_amount == pytest.approx(750_000.0)
    assert line.weighted_net == pytest.approx(line.net_amount * line.risk_weight)


def test_duplicate_risk_factor_keys_are_summed() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(sensitivity_id="cva-1", tag=SensitivityTag.CVA, amount=500_000.0),
            _sensitivity(sensitivity_id="cva-2", tag=SensitivityTag.CVA, amount=300_000.0),
        )
    )
    assert weighted[0].gross_cva_amount == pytest.approx(800_000.0)
