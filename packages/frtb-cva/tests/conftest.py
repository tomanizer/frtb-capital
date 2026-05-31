from __future__ import annotations

from datetime import date

import pytest
from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
)


@pytest.fixture
def sample_lineage() -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva-fixture",
        source_file="fixture.csv",
        source_row_id="row-001",
        source_column_map=(("EAD", "ead"),),
    )


@pytest.fixture
def sovereign_counterparty(sample_lineage: CvaSourceLineage) -> CvaCounterparty:
    return CvaCounterparty(
        counterparty_id="ctp-sovereign-ig",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-sovereign-ig",
        lineage=sample_lineage,
    )


@pytest.fixture
def sovereign_netting_set(sample_lineage: CvaSourceLineage) -> CvaNettingSet:
    return CvaNettingSet(
        netting_set_id="ns-sovereign-ig",
        counterparty_id="ctp-sovereign-ig",
        ead=1_000_000.0,
        effective_maturity=2.5,
        discount_factor=0.9400247793232364,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="row-ns-sovereign-ig",
        lineage=sample_lineage,
    )


@pytest.fixture
def reduced_context() -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="run-reduced-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )
