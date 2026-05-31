from __future__ import annotations

from frtb_cva import CvaRegulatoryProfile, calculate_cva_capital, input_hash, profile_content_hash


def test_repeated_runs_are_deterministic(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    first = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    second = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    assert first.total_cva_capital == second.total_cva_capital
    assert first.input_hash == second.input_hash
    assert first.profile_hash == profile_content_hash(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert input_hash(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    ) == first.input_hash
