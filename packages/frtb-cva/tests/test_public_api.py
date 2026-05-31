from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva import (
    CvaMethod,
    calculate_cva_capital,
    input_hash,
    serialize_cva_result,
    validate_cva_result_reconciliation,
)


def test_public_api_returns_reconciled_result(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    assert result.method is CvaMethod.BA_CVA_REDUCED
    assert result.profile_hash
    assert result.input_hash
    assert result.citations
    validate_cva_result_reconciliation(result)


def test_input_hash_is_deterministic(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    first = input_hash(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    second = input_hash(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    assert first == second


def test_serialize_result_is_json_ready(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    payload = serialize_cva_result(result)
    assert payload["method"] == CvaMethod.BA_CVA_REDUCED.value
    assert payload["ba_cva_reduced"] is not None


def test_full_ba_cva_fails_at_public_api(reduced_context, sovereign_counterparty, sovereign_netting_set) -> None:
    from frtb_cva import CvaCalculationContext

    context = CvaCalculationContext(
        run_id=reduced_context.run_id,
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=reduced_context.profile,
        method=CvaMethod.BA_CVA_FULL,
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="phase 1"):
        calculate_cva_capital(context, (sovereign_counterparty,), (sovereign_netting_set,))
