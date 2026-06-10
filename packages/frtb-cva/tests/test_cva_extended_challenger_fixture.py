from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaHedge,
    CvaInputError,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
    validate_cva_result_reconciliation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "cva_extended_challenger_v1"


def test_full_ba_fixture_covers_hedge_recognition_and_beta_floor() -> None:
    case = _load_case("full_ba_hedge_floor")
    expected = _load_expected("full_ba_hedge_floor")

    result = _calculate_case(case)

    validate_cva_result_reconciliation(result)
    assert result.total_cva_capital == pytest.approx(expected["total_cva_capital"])
    assert result.ba_cva_full is not None
    full = result.ba_cva_full
    assert full.k_full == pytest.approx(expected["k_full"])
    assert full.k_reduced == pytest.approx(expected["k_reduced"])
    assert full.k_hedged == pytest.approx(expected["k_hedged"])
    assert full.k_portfolio_hedged == pytest.approx(expected["k_portfolio_hedged"])
    assert full.beta == pytest.approx(expected["beta"])
    assert full.beta_floor_binding is expected["beta_floor_binding"]
    assert full.beta * full.k_reduced == pytest.approx(expected["beta_floor_term"])

    adjusted = dict(full.counterparty_adjusted_standalone)
    expected_adjusted = expected["counterparty_adjusted_standalone"]
    for counterparty_id, expected_value in expected_adjusted.items():
        assert adjusted[counterparty_id] == pytest.approx(expected_value)

    hedge_lines = {line.hedge_id: line for line in full.hedge_lines}
    for hedge_id, expected_line in expected["hedge_lines"].items():
        line = hedge_lines[hedge_id]
        assert line.r_hc == pytest.approx(expected_line["r_hc"])
        assert line.risk_weight == pytest.approx(expected_line["risk_weight"])
        assert line.snh_contribution == pytest.approx(expected_line["snh_contribution"])
        assert line.hma_contribution == pytest.approx(expected_line["hma_contribution"])
        assert line.index_contribution == pytest.approx(expected_line["index_contribution"])
        assert line.reason_code == expected_line["reason_code"]


def test_mixed_fixture_covers_carve_out_component_assembly() -> None:
    case = _load_case("mixed_carve_out")
    expected = _load_expected("mixed_carve_out")

    result = _calculate_case(case)

    validate_cva_result_reconciliation(result)
    assert result.method is CvaMethod.MIXED_CARVE_OUT
    assert result.total_cva_capital == pytest.approx(expected["total_cva_capital"])
    assert result.ba_cva_reduced is not None
    assert result.ba_cva_reduced.k_reduced == pytest.approx(expected["ba_cva_reduced"]["k_reduced"])
    assert result.ba_cva_reduced.sum_scva == pytest.approx(expected["ba_cva_reduced"]["sum_scva"])

    components = {item.method.value: item.total_capital for item in result.method_components}
    assert components == pytest.approx(expected["method_components"])
    audit_metadata = dict(result.audit_metadata)
    for key, expected_value in expected["audit_metadata"].items():
        assert audit_metadata[key] == expected_value
    _assert_sa_capitals(result.sa_cva_risk_class_capitals, expected)


def test_sa_multi_risk_fixture_covers_expected_outputs_and_index_routing() -> None:
    case = _load_case("sa_multi_risk_qualified_index")
    expected = _load_expected("sa_multi_risk_qualified_index")

    result = _calculate_case(case)

    validate_cva_result_reconciliation(result)
    assert result.method is CvaMethod.SA_CVA
    assert result.total_cva_capital == pytest.approx(expected["total_cva_capital"])
    _assert_sa_capitals(result.sa_cva_risk_class_capitals, expected)

    ccs = _risk_class_capital(
        result.sa_cva_risk_class_capitals,
        "COUNTERPARTY_CREDIT_SPREAD/DELTA",
    )
    assert tuple(bucket.bucket_id for bucket in ccs.bucket_capitals) == ("3",)


def test_qualified_index_fixture_fails_closed_without_required_remap_metadata() -> None:
    invalid = _load_payload()["invalid_cases"]["qualified_index_missing_remap_metadata"]

    with pytest.raises(CvaInputError, match=invalid["expected_error_match"]):
        _calculate_case(invalid)


def _assert_sa_capitals(capitals: tuple[Any, ...], expected: dict[str, Any]) -> None:
    expected_capitals = expected["sa_cva_risk_class_capitals"]
    assert {_risk_class_key(item) for item in capitals} == set(expected_capitals)
    for key, expected_capital in expected_capitals.items():
        capital = _risk_class_capital(capitals, key)
        assert capital.post_multiplier_capital == pytest.approx(
            expected_capital["post_multiplier_capital"]
        )
        buckets = {bucket.bucket_id: bucket for bucket in capital.bucket_capitals}
        assert set(buckets) == set(expected_capital["bucket_capitals"])
        for bucket_id, expected_bucket in expected_capital["bucket_capitals"].items():
            bucket = buckets[bucket_id]
            assert bucket.k_b == pytest.approx(expected_bucket["k_b"])
            assert bucket.s_b == pytest.approx(expected_bucket["s_b"])


def _risk_class_capital(capitals: tuple[Any, ...], key: str) -> Any:
    return next(item for item in capitals if _risk_class_key(item) == key)


def _risk_class_key(item: Any) -> str:
    return f"{item.risk_class.value}/{item.risk_measure.value}"


def _calculate_case(case: dict[str, Any]) -> Any:
    return calculate_cva_capital(
        _context(case["context"]),
        _counterparties(case.get("counterparties", [])),
        _netting_sets(case.get("netting_sets", [])),
        hedges=_hedges(case.get("hedges", [])),
        sensitivities=_sensitivities(case.get("sensitivities", [])),
    )


def _context(payload: dict[str, Any]) -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id=str(payload["run_id"]),
        calculation_date=date.fromisoformat(str(payload["calculation_date"])),
        base_currency=str(payload["base_currency"]),
        profile=CvaRegulatoryProfile(str(payload["profile"])),
        method=CvaMethod(str(payload["method"])),
        sa_cva_approved=bool(payload["sa_cva_approved"]),
        carve_out_netting_set_ids=tuple(payload.get("carve_out_netting_set_ids", ())),
        sa_cva_sensitivity_scope_evidence_id=payload.get("sa_cva_sensitivity_scope_evidence_id"),
    )


def _counterparties(payloads: list[dict[str, Any]]) -> tuple[CvaCounterparty, ...]:
    return tuple(
        CvaCounterparty(
            counterparty_id=str(payload["counterparty_id"]),
            desk_id=str(payload["desk_id"]),
            legal_entity=str(payload["legal_entity"]),
            sector=CvaSector(str(payload["sector"])),
            credit_quality=CreditQuality(str(payload["credit_quality"])),
            region=str(payload["region"]),
            source_row_id=str(payload["source_row_id"]),
            lineage=_lineage(payload),
        )
        for payload in payloads
    )


def _netting_sets(payloads: list[dict[str, Any]]) -> tuple[CvaNettingSet, ...]:
    return tuple(
        CvaNettingSet(
            netting_set_id=str(payload["netting_set_id"]),
            counterparty_id=str(payload["counterparty_id"]),
            ead=float(payload["ead"]),
            effective_maturity=float(payload["effective_maturity"]),
            discount_factor=float(payload["discount_factor"]),
            currency=str(payload["currency"]),
            sign_convention=str(payload["sign_convention"]),
            uses_imm_ead=bool(payload["uses_imm_ead"]),
            source_row_id=str(payload["source_row_id"]),
            carved_out_to_ba_cva=bool(payload.get("carved_out_to_ba_cva", False)),
            discount_factor_explicit=bool(payload.get("discount_factor_explicit", False)),
            lineage=_lineage(payload),
        )
        for payload in payloads
    )


def _hedges(payloads: list[dict[str, Any]]) -> tuple[CvaHedge, ...]:
    return tuple(_hedge(payload) for payload in payloads)


def _hedge(payload: dict[str, Any]) -> CvaHedge:
    hedge_type = payload.get("hedge_type")
    resolved_hedge_type = None
    if hedge_type is not None:
        resolved_hedge_type = BaCvaHedgeType(str(hedge_type))

    return CvaHedge(
        hedge_id=str(payload["hedge_id"]),
        source_row_id=str(payload["source_row_id"]),
        counterparty_id=str(payload["counterparty_id"]),
        hedge_type=resolved_hedge_type,
        notional=float(payload["notional"]),
        remaining_maturity=float(payload["remaining_maturity"]),
        discount_factor=float(payload["discount_factor"]),
        reference_sector=CvaSector(str(payload["reference_sector"])),
        reference_credit_quality=CreditQuality(str(payload["reference_credit_quality"])),
        reference_region=str(payload["reference_region"]),
        reference_relation=HedgeReferenceRelation(str(payload["reference_relation"])),
        eligibility=HedgeEligibility(str(payload["eligibility"])),
        is_internal=bool(payload["is_internal"]),
        discount_factor_explicit=bool(payload.get("discount_factor_explicit", False)),
        eligibility_evidence_id=payload.get("eligibility_evidence_id"),
        lineage=_lineage(payload),
    )


def _sensitivities(payloads: list[dict[str, Any]]) -> tuple[SaCvaSensitivity, ...]:
    return tuple(_sensitivity(payload) for payload in payloads)


def _sensitivity(payload: dict[str, Any]) -> SaCvaSensitivity:
    index_treatment = payload.get("index_treatment")
    resolved_index_treatment = None
    if index_treatment is not None:
        resolved_index_treatment = SaCvaIndexTreatment(str(index_treatment))

    index_dominant_sector = payload.get("index_dominant_sector")
    resolved_index_dominant_sector = None
    if index_dominant_sector is not None:
        resolved_index_dominant_sector = CvaSector(str(index_dominant_sector))

    return SaCvaSensitivity(
        sensitivity_id=str(payload["sensitivity_id"]),
        risk_class=SaCvaRiskClass(str(payload["risk_class"])),
        risk_measure=SaCvaRiskMeasure(str(payload["risk_measure"])),
        sensitivity_tag=SensitivityTag(str(payload["sensitivity_tag"])),
        bucket_id=str(payload["bucket_id"]),
        risk_factor_key=str(payload["risk_factor_key"]),
        amount=float(payload["amount"]),
        amount_currency=str(payload["amount_currency"]),
        sign_convention=str(payload["sign_convention"]),
        source_row_id=str(payload["source_row_id"]),
        tenor=payload.get("tenor"),
        volatility_input=payload.get("volatility_input"),
        hedge_id=payload.get("hedge_id"),
        index_treatment=resolved_index_treatment,
        index_max_sector_weight=payload.get("index_max_sector_weight"),
        index_homogeneous_sector_quality=bool(
            payload.get("index_homogeneous_sector_quality", False)
        ),
        index_dominant_sector=resolved_index_dominant_sector,
        index_remap_bucket_id=payload.get("index_remap_bucket_id"),
        lineage=_lineage(payload),
    )


def _lineage(payload: dict[str, Any]) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva-fixture",
        source_file="cva_extended_challenger_v1/inputs.json",
        source_row_id=str(payload["source_row_id"]),
        source_column_map=(("amount", "amount"),),
    )


def _load_case(case_id: str) -> dict[str, Any]:
    return _load_payload()["cases"][case_id]


def _load_expected(case_id: str) -> dict[str, Any]:
    payload = _load_json("expected_outputs.json")
    assert payload["schema_version"] == 1
    return payload["cases"][case_id]


def _load_payload() -> dict[str, Any]:
    payload = _load_json("inputs.json")
    assert payload["schema_version"] == 1
    return payload


def _load_json(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except ValueError as exc:
            message = f"failed to parse CVA challenger fixture {name}: {exc}"
            raise ValueError(message) from exc
