"""Tests for CVA risk-factor-adjacent metadata drilldown rows."""

from __future__ import annotations

from datetime import date

from frtb_cva.data_models import (
    BaCvaStandAloneLine,
    CreditQuality,
    CvaCapitalResult,
    CvaMethod,
    CvaSector,
    SaCvaBucketCapital,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
)
from frtb_cva.risk_factor_metadata import build_cva_risk_factor_metadata_rows


def test_cva_risk_factor_metadata_rows_preserve_counterparty_and_sensitivity_ids() -> None:
    ba_line = BaCvaStandAloneLine(
        netting_set_id="netting-1",
        counterparty_id="cp-1",
        sector=CvaSector.FINANCIALS,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        ead=100.0,
        effective_maturity=1.0,
        discount_factor=0.98,
        alpha=1.4,
        risk_weight=0.005,
        standalone_capital=0.686,
        currency="USD",
        source_row_id="netting-row-1",
        citations=(),
    )
    bucket = SaCvaBucketCapital(
        bucket_id="16",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        k_b=2.0,
        s_b=1.0,
        sensitivity_ids=("sens-2", "sens-1"),
        citations=(),
    )
    risk_class = SaCvaRiskClassCapital(
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        pre_multiplier_capital=2.0,
        post_multiplier_capital=2.0,
        m_cva=1.0,
        bucket_capitals=(bucket,),
        citations=(),
    )
    result = CvaCapitalResult(
        run_id="run-1",
        calculation_date=date(2025, 1, 2),
        base_currency="USD",
        profile_id="BASEL_MAR50_2020",
        profile_hash="profile",
        input_hash="input",
        method=CvaMethod.SA_CVA,
        total_cva_capital=2.686,
        ba_cva_reduced=None,
        ba_cva_full=None,
        ba_cva_counterparty_capitals=(),
        ba_cva_netting_set_lines=(ba_line,),
        sa_cva_risk_class_capitals=(risk_class,),
        citations=(),
    )

    rows = build_cva_risk_factor_metadata_rows(result)

    ba_rows = [row for row in rows if row.risk_class == "BA_CVA"]
    sa_rows = [row for row in rows if row.risk_class == "REFERENCE_CREDIT_SPREAD"]
    assert ba_rows[0].counterparty_id == "cp-1"
    assert ba_rows[0].source_row_id == "netting-row-1"
    assert ba_rows[0].sector == "FINANCIALS"
    assert sa_rows[0].bucket_id == "16"
    assert sa_rows[0].source_row_id is None
    assert sa_rows[0].sensitivity_ids == ("sens-1", "sens-2")

    object.__setattr__(result, "ba_cva_netting_set_lines", None)
    object.__setattr__(result, "sa_cva_risk_class_capitals", None)
    assert build_cva_risk_factor_metadata_rows(result) == ()
