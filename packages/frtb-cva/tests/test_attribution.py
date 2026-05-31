from __future__ import annotations

from frtb_cva import CvaMethod, calculate_cva_capital
from frtb_cva.attribution import attribute_cva_capital


def test_attribution_does_not_change_capital(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    attribution = attribute_cva_capital(result)
    assert attribution.total_capital == result.total_cva_capital
    assert result.method is CvaMethod.BA_CVA_REDUCED
    assert attribution.unsupported_branches
