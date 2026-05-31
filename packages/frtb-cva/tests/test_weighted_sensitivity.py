from __future__ import annotations

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.reference_data import girr_delta_risk_weight
from frtb_cva.weighted_sensitivity import compute_weighted_sensitivities


def _sensitivity(
    *,
    sensitivity_id: str,
    tag: SensitivityTag,
    amount: float,
    tenor: str = "5y",
    hedge_id: str | None = None,
    bucket_id: str = "USD",
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=tag,
        bucket_id=bucket_id,
        risk_factor_key=tenor,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-{sensitivity_id}",
        hedge_id=hedge_id,
    )


def test_girr_delta_weighted_sensitivity_preserves_gross_and_net() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(sensitivity_id="cva-1", tag=SensitivityTag.CVA, amount=1_000_000.0),
            _sensitivity(
                sensitivity_id="hdg-s1",
                tag=SensitivityTag.HDG,
                amount=250_000.0,
                hedge_id="hedge-A",
            ),
        ),
        eligible_hedge_ids=frozenset({"hedge-A"}),
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


def test_hdg_sensitivity_filtered_by_hedge_id_not_sensitivity_id() -> None:
    """HDG filtering uses hedge_id, not sensitivity_id (regression for review finding #1)."""
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(sensitivity_id="cva-1", tag=SensitivityTag.CVA, amount=1_000_000.0),
            _sensitivity(
                sensitivity_id="s-unrelated-id",
                tag=SensitivityTag.HDG,
                amount=250_000.0,
                hedge_id="hedge-A",
            ),
        ),
        eligible_hedge_ids=frozenset({"hedge-A"}),
    )
    assert len(weighted) == 1
    assert weighted[0].gross_hedge_amount == pytest.approx(250_000.0)


def test_hdg_sensitivity_dropped_when_no_eligible_hedges_provided() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(sensitivity_id="cva-1", tag=SensitivityTag.CVA, amount=1_000_000.0),
            _sensitivity(
                sensitivity_id="s-hdg-1",
                tag=SensitivityTag.HDG,
                amount=250_000.0,
                hedge_id="hedge-A",
            ),
        ),
    )
    assert len(weighted) == 1
    assert weighted[0].gross_hedge_amount == pytest.approx(0.0)


def test_other_currency_risk_weight_scaled_per_mar50_57() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(
                sensitivity_id="cva-chf",
                tag=SensitivityTag.CVA,
                amount=1.0,
                bucket_id="CHF",
            ),
        ),
        reporting_currency="USD",
    )
    base_risk_weight, _ = girr_delta_risk_weight("5y")
    assert weighted[0].risk_weight == pytest.approx(base_risk_weight * 1.4)
    assert "basel_mar50_57" in weighted[0].citations


def test_reporting_currency_uses_specified_currency_tables() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(
                sensitivity_id="cva-chf",
                tag=SensitivityTag.CVA,
                amount=1.0,
                bucket_id="CHF",
            ),
        ),
        reporting_currency="CHF",
    )
    base_risk_weight, _ = girr_delta_risk_weight("5y")
    assert weighted[0].risk_weight == pytest.approx(base_risk_weight)


def test_hdg_sensitivity_dropped_when_hedge_not_eligible() -> None:
    weighted = compute_weighted_sensitivities(
        (
            _sensitivity(sensitivity_id="cva-1", tag=SensitivityTag.CVA, amount=1_000_000.0),
            _sensitivity(
                sensitivity_id="s-hdg-1",
                tag=SensitivityTag.HDG,
                amount=250_000.0,
                hedge_id="hedge-B",
            ),
        ),
        eligible_hedge_ids=frozenset({"hedge-A"}),
    )
    assert len(weighted) == 1
    assert weighted[0].gross_hedge_amount == pytest.approx(0.0)
