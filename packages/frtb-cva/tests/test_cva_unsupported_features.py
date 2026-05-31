from __future__ import annotations

from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
)


@pytest.mark.parametrize(
    "method",
    [CvaMethod.BA_CVA_FULL, CvaMethod.MIXED_CARVE_OUT],
)
def test_unsupported_methods_fail_closed(method: CvaMethod) -> None:
    from frtb_cva import resolve_calculation_method

    context = CvaCalculationContext(
        run_id="run-unsupported",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=method,
        sa_cva_approved=True,
        carve_out_netting_set_ids=("ns-1",) if method is CvaMethod.MIXED_CARVE_OUT else (),
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="phase 1"):
        resolve_calculation_method(context)
