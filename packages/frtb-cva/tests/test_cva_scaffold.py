from datetime import date

import pytest
from frtb_common import ImplementationStatus
from frtb_cva import (
    PACKAGE_METADATA,
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    __version__,
    calculate_cva_capital,
)


def _lineage(row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="test",
        source_file="fixture.csv",
        source_row_id=row_id,
    )


def test_cva_package_imports_with_partial_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-cva"
    assert PACKAGE_METADATA.import_name == "frtb_cva"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.PARTIAL


def test_reduced_ba_cva_produces_capital_result() -> None:
    counterparty = CvaCounterparty(
        counterparty_id="ctp-1",
        desk_id="desk-a",
        legal_entity="entity-a",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-1",
        lineage=_lineage("row-ctp-1"),
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id="ctp-1",
        ead=1_000_000.0,
        effective_maturity=2.5,
        discount_factor=1.0,
        currency="USD",
        sign_convention="positive_loss",
        uses_imm_ead=True,
        source_row_id="row-ns-1",
        lineage=_lineage("row-ns-1"),
    )
    context = CvaCalculationContext(
        run_id="run-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )
    result = calculate_cva_capital(context, (counterparty,), (netting_set,))
    assert result.total_cva_capital == pytest.approx(11_375.0)
    assert result.method is CvaMethod.BA_CVA_REDUCED
    assert len(result.ba_cva_netting_set_lines) == 1


def test_sa_cva_girr_delta_produces_capital_result() -> None:
    from frtb_cva import SaCvaRiskClass, SaCvaRiskMeasure, SaCvaSensitivity, SensitivityTag

    context = CvaCalculationContext(
        run_id="run-2",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
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
    result = calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
    assert result.method is CvaMethod.SA_CVA
    assert result.total_cva_capital > 0.0
    assert len(result.sa_cva_risk_class_capitals) == 1
