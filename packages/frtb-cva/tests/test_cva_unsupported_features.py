from __future__ import annotations

from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
)


def test_materiality_threshold_fails_at_public_api(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    from frtb_cva import CvaInputError

    context = CvaCalculationContext(
        run_id=reduced_context.run_id,
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=reduced_context.profile,
        method=CvaMethod.BA_CVA_REDUCED,
        materiality_threshold_elected=True,
    )
    with pytest.raises(CvaInputError, match="materiality-threshold"):
        calculate_cva_capital(context, (sovereign_counterparty,), (sovereign_netting_set,))


def test_unsupported_profile_fails_at_public_api() -> None:
    context = CvaCalculationContext(
        run_id="run-unsupported-profile",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.US_NPR20_VB,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-girr-5y",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-girr-5y",
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError):
        calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))


def test_ccs_vega_fails_at_public_api() -> None:
    from frtb_cva import CvaInputError

    context = CvaCalculationContext(
        run_id="run-ccs-vega",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-ccs-vega",
        risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="2",
        risk_factor_key="CP1|INVESTMENT_GRADE",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-ccs-vega",
        volatility_input=0.2,
    )
    with pytest.raises(CvaInputError, match="CCS vega"):
        calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
