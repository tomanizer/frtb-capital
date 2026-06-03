from __future__ import annotations

from frtb_common.impact import CapitalImpact, ImpactMethod

from frtb_cva import calculate_cva_capital
from frtb_cva.impact import assess_cva_capital_impact


def test_capital_impact_returns_shared_type(
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
    assert isinstance(impact, CapitalImpact)


def test_capital_impact_method_is_finite_difference(
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
    assert impact.method == ImpactMethod.FINITE_DIFFERENCE


def test_capital_impact_component_is_frtb_cva(
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
    assert impact.component == "frtb_cva"


def test_capital_impact_delta_equals_candidate_minus_baseline(
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
    assert impact.delta == candidate.total_cva_capital - baseline.total_cva_capital
    assert impact.delta == 0.0


def test_capital_impact_input_hash_matches_result(
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
    assert impact.baseline_input_hash == baseline.input_hash
    assert impact.candidate_input_hash == candidate.input_hash


def test_capital_impact_profile_hash_matches_result(
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
    assert impact.baseline_profile_hash == baseline.profile_hash
    assert impact.candidate_profile_hash == candidate.profile_hash
