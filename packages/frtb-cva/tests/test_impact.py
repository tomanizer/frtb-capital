from __future__ import annotations

from frtb_cva import calculate_cva_capital
from frtb_cva.impact import assess_cva_capital_impact


def test_capital_impact_reports_finite_difference(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    baseline = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    candidate = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    impact = assess_cva_capital_impact(baseline, candidate)
    assert impact.method == "finite_difference"
    assert impact.delta == 0.0
