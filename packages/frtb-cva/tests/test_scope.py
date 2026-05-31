from __future__ import annotations

from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CvaCalculationContext,
    CvaInputError,
    CvaMethod,
    CvaRegulatoryProfile,
    resolve_calculation_method,
    validate_method_selection,
)


def test_ba_cva_reduced_is_default(resolved_context=None) -> None:
    context = CvaCalculationContext(
        run_id="run-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
    )
    scope = resolve_calculation_method(context)
    assert scope.method is CvaMethod.BA_CVA_REDUCED
    assert scope.audit_metadata[0] == ("requested_method", "BA_CVA_REDUCED")


def test_sa_cva_requires_approval() -> None:
    context = CvaCalculationContext(
        run_id="run-2",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=False,
    )
    with pytest.raises(CvaInputError, match="sa_cva_approved"):
        resolve_calculation_method(context)


def test_sa_cva_resolves_when_approved() -> None:
    context = CvaCalculationContext(
        run_id="run-3",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    scope = validate_method_selection(context)
    assert scope.method is CvaMethod.SA_CVA


def test_materiality_threshold_fails_closed() -> None:
    context = CvaCalculationContext(
        run_id="run-4",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        materiality_threshold_elected=True,
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match=r"MAR50\.9"):
        resolve_calculation_method(context)


def test_unknown_carve_out_id_fails(sovereign_counterparty, sovereign_netting_set) -> None:
    context = CvaCalculationContext(
        run_id="run-5",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        carve_out_netting_set_ids=("missing-ns",),
    )
    with pytest.raises(CvaInputError, match="carve-out netting set"):
        validate_method_selection(
            context,
            netting_sets=(sovereign_netting_set,),
        )
