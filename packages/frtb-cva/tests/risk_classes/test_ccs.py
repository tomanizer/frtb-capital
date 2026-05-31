from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.risk_classes.ccs import calculate_ccs_delta_capital
from frtb_cva.validation import CvaInputError


def _ccs_sensitivity(
    *,
    bucket: str = "2",
    entity: str = "CP1",
    quality: str = "INVESTMENT_GRADE",
    tenor: str = "5y",
    amount: float = 1_000_000.0,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-ccs-{entity}-{tenor}",
        risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key=f"{entity}|{quality}",
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-ccs-{entity}-{tenor}",
    )


def test_ccs_delta_single_entity_reconciles() -> None:
    capital = calculate_ccs_delta_capital((_ccs_sensitivity(amount=2_000_000.0),))
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.05)


def test_ccs_delta_unrelated_same_quality_uses_cited_rho() -> None:
    capital = calculate_ccs_delta_capital(
        (
            _ccs_sensitivity(entity="CP1", tenor="5y", amount=1_000_000.0),
            _ccs_sensitivity(entity="CP2", tenor="5y", amount=1_000_000.0),
        ),
    )
    ws = 1_000_000.0 * 0.05
    kb = math.sqrt(ws**2 + ws**2 + 2 * 0.5 * ws * ws)
    assert capital.bucket_capitals[0].k_b == pytest.approx(kb)


def test_ccs_qualified_index_bucket_fails_closed() -> None:
    with pytest.raises(CvaInputError, match="qualified-index"):
        calculate_ccs_delta_capital((_ccs_sensitivity(bucket="8"),))
