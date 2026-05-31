from __future__ import annotations

import json
from datetime import date

from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
    serialize_cva_result,
    validate_cva_result_reconciliation,
)


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


def test_sa_cva_audit_payload_includes_risk_class_breakdown() -> None:
    context = CvaCalculationContext(
        run_id="run-sa-audit",
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
    payload = serialize_cva_result(result)
    risk_class_rows = payload["sa_cva_risk_class_capitals"]
    assert len(risk_class_rows) == 1
    assert risk_class_rows[0]["risk_class"] == "GIRR"
    assert len(risk_class_rows[0]["bucket_capitals"]) == 1
    assert risk_class_rows[0]["bucket_capitals"][0]["k_b"] > 0.0
    validate_cva_result_reconciliation(result)
