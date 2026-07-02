from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest
from frtb_cva import (
    CvaCalculationContext,
    CvaInputError,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_cva_counterparty_batch_from_columns,
    build_cva_netting_set_batch_from_columns,
    build_sa_cva_sensitivity_batch_from_columns,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    serialize_cva_result,
    validate_cva_result_reconciliation,
)


def _audit_context(
    method: CvaMethod,
    *,
    sa_cva_approved: bool = False,
    carve_out_netting_set_ids: tuple[str, ...] = (),
    sa_cva_sensitivity_scope_evidence_id: str | None = None,
) -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id=f"run-audit-{method.value.lower()}",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=method,
        sa_cva_approved=sa_cva_approved,
        carve_out_netting_set_ids=carve_out_netting_set_ids,
        sa_cva_sensitivity_scope_evidence_id=sa_cva_sensitivity_scope_evidence_id,
    )


def _audit_counterparty_batch():
    return build_cva_counterparty_batch_from_columns(
        counterparty_ids=["cp-1"],
        desk_ids=["desk-1"],
        legal_entities=["LE-001"],
        sectors=["SOVEREIGN"],
        credit_qualities=["INVESTMENT_GRADE"],
        regions=["EMEA"],
        source_row_ids=["cp-row-1"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["counterparties.csv"],
    )


def _audit_netting_set_batch():
    return build_cva_netting_set_batch_from_columns(
        netting_set_ids=["ns-1"],
        counterparty_ids=["cp-1"],
        eads=[100_000.0],
        effective_maturities=[2.5],
        discount_factors=[0.98],
        currencies=["USD"],
        sign_conventions=["non_negative"],
        uses_imm_eads=[False],
        carved_out_to_ba_cva=[True],
        source_row_ids=["ns-row-1"],
    )


def _audit_sensitivity_batch():
    return build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-1"],
        risk_classes=["GIRR"],
        risk_measures=["DELTA"],
        sensitivity_tags=["CVA"],
        bucket_ids=["USD"],
        risk_factor_keys=["5y"],
        amounts=[1_000.0],
        amount_currencies=["USD"],
        sign_conventions=["positive_loss"],
        source_row_ids=["sens-row-1"],
        tenors=["5y"],
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
    assert decoded["ba_cva_netting_set_lines"][0]["exposure_time_series_id"] is None
    validate_cva_result_reconciliation(result)


def test_audit_payload_preserves_ba_exposure_time_series_id(reduced_context) -> None:
    counterparty_batch = _audit_counterparty_batch()
    netting_set_batch = build_cva_netting_set_batch_from_columns(
        netting_set_ids=["ns-1"],
        counterparty_ids=["cp-1"],
        eads=[100_000.0],
        effective_maturities=[2.5],
        discount_factors=[0.98],
        currencies=["USD"],
        sign_conventions=["non_negative"],
        uses_imm_eads=[False],
        source_row_ids=["ns-row-1"],
        exposure_time_series_ids=["ts-cva-exposure-ns-1"],
    )

    result = calculate_cva_capital_from_batches(
        reduced_context,
        counterparty_batch,
        netting_set_batch,
    ).result
    payload = serialize_cva_result(result)

    assert result.ba_cva_netting_set_lines[0].exposure_time_series_id == ("ts-cva-exposure-ns-1")
    assert payload["ba_cva_netting_set_lines"][0]["exposure_time_series_id"] == (
        "ts-cva-exposure-ns-1"
    )


def test_audit_reconciliation_rejects_tampered_ba_reduced_results(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    assert result.ba_cva_reduced is not None

    with pytest.raises(CvaInputError, match="hash must be a sha256 hex digest"):
        validate_cva_result_reconciliation(replace(result, input_hash="not-a-digest"))
    with pytest.raises(CvaInputError, match="hash must be a sha256 hex digest"):
        validate_cva_result_reconciliation(replace(result, profile_hash="g" * 64))
    with pytest.raises(CvaInputError, match="reduced result is required"):
        validate_cva_result_reconciliation(replace(result, ba_cva_reduced=None))
    with pytest.raises(CvaInputError, match="does not reconcile to reduced BA-CVA"):
        validate_cva_result_reconciliation(
            replace(result, total_cva_capital=result.total_cva_capital + 1.0)
        )
    with pytest.raises(CvaInputError, match="netting-set lines do not reconcile"):
        validate_cva_result_reconciliation(replace(result, ba_cva_netting_set_lines=()))
    with pytest.raises(CvaInputError, match="counterparty capitals do not reconcile"):
        validate_cva_result_reconciliation(replace(result, ba_cva_counterparty_capitals=()))

    counterparty = result.ba_cva_reduced.counterparty_capitals[0]
    bad_counterparty = replace(
        counterparty,
        standalone_capital=counterparty.standalone_capital + 1.0,
    )
    bad_reduced = replace(result.ba_cva_reduced, counterparty_capitals=(bad_counterparty,))
    with pytest.raises(CvaInputError, match="stand-alone capital does not reconcile"):
        validate_cva_result_reconciliation(
            replace(
                result,
                ba_cva_reduced=bad_reduced,
                ba_cva_counterparty_capitals=(bad_counterparty,),
            )
        )

    with pytest.raises(CvaInputError, match="sum_scva does not reconcile"):
        validate_cva_result_reconciliation(
            replace(
                result,
                ba_cva_reduced=replace(
                    result.ba_cva_reduced,
                    sum_scva=result.ba_cva_reduced.sum_scva + 1.0,
                ),
            )
        )
    with pytest.raises(CvaInputError, match="portfolio capital does not reconcile"):
        validate_cva_result_reconciliation(
            replace(
                result,
                ba_cva_reduced=replace(
                    result.ba_cva_reduced,
                    k_portfolio=result.ba_cva_reduced.k_portfolio + 1.0,
                ),
            )
        )
    with pytest.raises(CvaInputError, match="discount scalar"):
        bad_reduced = replace(
            result.ba_cva_reduced,
            k_reduced=result.ba_cva_reduced.k_reduced + 1.0,
        )
        validate_cva_result_reconciliation(
            replace(result, ba_cva_reduced=bad_reduced, total_cva_capital=bad_reduced.k_reduced)
        )


def test_audit_reconciliation_rejects_tampered_full_ba_results(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        _audit_context(CvaMethod.BA_CVA_FULL),
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    assert result.ba_cva_full is not None

    with pytest.raises(CvaInputError, match="full result is required"):
        validate_cva_result_reconciliation(replace(result, ba_cva_full=None))
    with pytest.raises(CvaInputError, match="full BA-CVA capital"):
        validate_cva_result_reconciliation(
            replace(
                result,
                ba_cva_full=replace(result.ba_cva_full, k_full=result.ba_cva_full.k_full + 1.0),
            )
        )

    floor_breach = replace(
        result.ba_cva_full,
        k_full=result.ba_cva_full.beta * result.ba_cva_full.k_reduced - 1.0,
    )
    with pytest.raises(CvaInputError, match="below beta floor"):
        validate_cva_result_reconciliation(
            replace(result, ba_cva_full=floor_breach, total_cva_capital=floor_breach.k_full)
        )


def test_audit_reconciliation_rejects_tampered_mixed_method_results() -> None:
    result = calculate_cva_capital_from_batches(
        _audit_context(
            CvaMethod.MIXED_CARVE_OUT,
            sa_cva_approved=True,
            carve_out_netting_set_ids=("ns-1",),
            sa_cva_sensitivity_scope_evidence_id="audit-sa-slice-evidence",
        ),
        _audit_counterparty_batch(),
        _audit_netting_set_batch(),
        sensitivities=_audit_sensitivity_batch(),
    ).result

    with pytest.raises(CvaInputError, match="method component totals"):
        validate_cva_result_reconciliation(replace(result, method_components=()))
    with pytest.raises(CvaInputError, match="mixed-method components"):
        validate_cva_result_reconciliation(
            replace(result, total_cva_capital=result.total_cva_capital + 1.0)
        )


def test_audit_reconciliation_rejects_tampered_sa_results() -> None:
    result = calculate_cva_capital_from_batches(
        _audit_context(CvaMethod.SA_CVA, sa_cva_approved=True),
        sensitivities=_audit_sensitivity_batch(),
    ).result
    risk_class = result.sa_cva_risk_class_capitals[0]
    bucket = risk_class.bucket_capitals[0]

    with pytest.raises(CvaInputError, match="at least one risk-class capital record"):
        validate_cva_result_reconciliation(replace(result, sa_cva_risk_class_capitals=()))
    with pytest.raises(CvaInputError, match="SA-CVA risk-class totals"):
        validate_cva_result_reconciliation(
            replace(result, total_cva_capital=result.total_cva_capital + 1.0)
        )

    bad_post = replace(
        risk_class,
        post_multiplier_capital=risk_class.post_multiplier_capital + 1.0,
    )
    with pytest.raises(CvaInputError, match="post-multiplier capital"):
        validate_cva_result_reconciliation(
            replace(
                result,
                total_cva_capital=bad_post.post_multiplier_capital,
                sa_cva_risk_class_capitals=(bad_post,),
            )
        )

    empty_bucket = replace(risk_class, bucket_capitals=())
    with pytest.raises(CvaInputError, match="at least one bucket capital"):
        validate_cva_result_reconciliation(
            replace(result, sa_cva_risk_class_capitals=(empty_bucket,))
        )

    shifted_bucket = replace(bucket, k_b=bucket.k_b + 1.0)
    with pytest.raises(CvaInputError, match="pre-multiplier capital"):
        validate_cva_result_reconciliation(
            replace(
                result,
                sa_cva_risk_class_capitals=(
                    replace(risk_class, bucket_capitals=(shifted_bucket,)),
                ),
            )
        )


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
    assert risk_class_rows[0]["bucket_capitals"][0]["sensitivity_ids"] == ["sens-girr-5y"]
    assert risk_class_rows[0]["bucket_capitals"][0]["volatility_surface_ids"] == []
    assert risk_class_rows[0]["bucket_capitals"][0]["volatility_surface_point_ids"] == []
    assert risk_class_rows[0]["bucket_capitals"][0]["shock_ids"] == []
    validate_cva_result_reconciliation(result)


def test_sa_cva_vega_audit_payload_preserves_surface_provenance() -> None:
    context = CvaCalculationContext(
        run_id="run-sa-vega-audit",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-girr-vega-rate",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="IR_VOL",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-girr-vega-rate",
        volatility_input=0.25,
        volatility_surface_id="surface-usd-swaption",
        volatility_surface_point_id="surface-usd-swaption:rate:atm",
        shock_id="shock-cva-vega-up",
    )

    result = calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
    payload = serialize_cva_result(result)
    bucket = result.sa_cva_risk_class_capitals[0].bucket_capitals[0]
    bucket_payload = payload["sa_cva_risk_class_capitals"][0]["bucket_capitals"][0]

    assert bucket.volatility_surface_ids == ("surface-usd-swaption",)
    assert bucket.volatility_surface_point_ids == ("surface-usd-swaption:rate:atm",)
    assert bucket.shock_ids == ("shock-cva-vega-up",)
    assert bucket_payload["volatility_surface_ids"] == ["surface-usd-swaption"]
    assert bucket_payload["volatility_surface_point_ids"] == ["surface-usd-swaption:rate:atm"]
    assert bucket_payload["shock_ids"] == ["shock-cva-vega-up"]
    assert result.total_cva_capital > 0.0
    validate_cva_result_reconciliation(result)
