from __future__ import annotations

import json

from frtb_cva import calculate_cva_capital, serialize_cva_result, validate_cva_result_reconciliation


def test_audit_payload_round_trip_is_stable(
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
    encoded = json.dumps(payload, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["input_hash"] == result.input_hash
    assert decoded["profile_hash"] == result.profile_hash
    validate_cva_result_reconciliation(result)
