from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date

import pytest
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaBatchCapitalCalculation,
    CvaCalculationContext,
    CvaCapitalResult,
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
    build_cva_counterparty_batch_from_counterparties,
    build_cva_hedge_batch_from_hedges,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    validate_cva_result_reconciliation,
)
from frtb_cva.sa_cva_reference_data import GIRR_VEGA_RATE_FACTOR


def _lineage(source_file: str, row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic",
        source_file=source_file,
        source_row_id=row_id,
    )


def _counterparties() -> tuple[CvaCounterparty, ...]:
    return (
        CvaCounterparty(
            counterparty_id="cp-sovereign",
            desk_id="desk-cva",
            legal_entity="LE-001",
            sector=CvaSector.SOVEREIGN,
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            region="EMEA",
            source_row_id="row-cp-sovereign",
            lineage=_lineage("counterparties.csv", "row-cp-sovereign"),
        ),
        CvaCounterparty(
            counterparty_id="cp-financial",
            desk_id="desk-cva",
            legal_entity="LE-001",
            sector=CvaSector.FINANCIALS,
            credit_quality=CreditQuality.INVESTMENT_GRADE,
            region="EMEA",
            source_row_id="row-cp-financial",
            lineage=_lineage("counterparties.csv", "row-cp-financial"),
        ),
    )


def _netting_sets(*, carve_out_sovereign: bool = False) -> tuple[CvaNettingSet, ...]:
    return (
        CvaNettingSet(
            netting_set_id="ns-sovereign",
            counterparty_id="cp-sovereign",
            ead=100_000.0,
            effective_maturity=2.5,
            discount_factor=0.98,
            currency="USD",
            sign_convention="non_negative",
            uses_imm_ead=False,
            source_row_id="row-ns-sovereign",
            carved_out_to_ba_cva=carve_out_sovereign,
            discount_factor_explicit=True,
            lineage=_lineage("netting_sets.csv", "row-ns-sovereign"),
        ),
        CvaNettingSet(
            netting_set_id="ns-financial",
            counterparty_id="cp-financial",
            ead=200_000.0,
            effective_maturity=1.5,
            discount_factor=0.99,
            currency="USD",
            sign_convention="non_negative",
            uses_imm_ead=False,
            source_row_id="row-ns-financial",
            discount_factor_explicit=True,
            lineage=_lineage("netting_sets.csv", "row-ns-financial"),
        ),
    )


def _ba_hedges() -> tuple[CvaHedge, ...]:
    return (
        CvaHedge(
            hedge_id="h-single-name",
            source_row_id="row-h-single-name",
            counterparty_id="cp-sovereign",
            hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
            notional=25_000.0,
            remaining_maturity=2.0,
            discount_factor=0.99,
            reference_sector=CvaSector.SOVEREIGN,
            reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
            reference_region="EMEA",
            reference_relation=HedgeReferenceRelation.DIRECT,
            eligibility=HedgeEligibility.ELIGIBLE,
            is_internal=False,
            eligibility_evidence_id="eligibility-h-single-name",
            lineage=_lineage("hedges.csv", "row-h-single-name"),
        ),
        CvaHedge(
            hedge_id="h-index",
            source_row_id="row-h-index",
            counterparty_id="cp-financial",
            hedge_type=BaCvaHedgeType.INDEX_CDS,
            notional=50_000.0,
            remaining_maturity=3.0,
            discount_factor=0.98,
            reference_sector=CvaSector.FINANCIALS,
            reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
            reference_region="EMEA",
            reference_relation=HedgeReferenceRelation.SAME_SECTOR_AND_REGION,
            eligibility=HedgeEligibility.ELIGIBLE,
            is_internal=False,
            eligibility_evidence_id="eligibility-h-index",
            lineage=_lineage("hedges.csv", "row-h-index"),
        ),
        CvaHedge(
            hedge_id="h-ineligible",
            source_row_id="row-h-ineligible",
            counterparty_id="cp-financial",
            hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
            notional=20_000.0,
            remaining_maturity=1.0,
            discount_factor=0.97,
            reference_sector=CvaSector.FINANCIALS,
            reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
            reference_region="EMEA",
            reference_relation=HedgeReferenceRelation.DIRECT,
            eligibility=HedgeEligibility.INELIGIBLE,
            is_internal=False,
            rejection_reason="tranched_credit_derivative",
            lineage=_lineage("hedges.csv", "row-h-ineligible"),
        ),
    )


def _context(
    method: CvaMethod,
    run_id: str,
    *,
    sa_cva_approved: bool = False,
    carve_out_netting_set_ids: tuple[str, ...] = (),
    sa_cva_sensitivity_scope_evidence_id: str | None = None,
) -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=method,
        sa_cva_approved=sa_cva_approved,
        carve_out_netting_set_ids=carve_out_netting_set_ids,
        sa_cva_sensitivity_scope_evidence_id=sa_cva_sensitivity_scope_evidence_id,
        desk_id="desk-cva",
        legal_entity="LE-001",
    )


def _batch_result(
    context: CvaCalculationContext,
    counterparties: Iterable[CvaCounterparty] = (),
    netting_sets: Iterable[CvaNettingSet] = (),
    *,
    hedges: Iterable[CvaHedge] = (),
    sensitivities: Iterable[SaCvaSensitivity] = (),
) -> CvaBatchCapitalCalculation:
    counterparty_rows = tuple(counterparties)
    netting_set_rows = tuple(netting_sets)
    hedge_rows = tuple(hedges)
    sensitivity_rows = tuple(sensitivities)
    return calculate_cva_capital_from_batches(
        context,
        build_cva_counterparty_batch_from_counterparties(counterparty_rows)
        if counterparty_rows
        else None,
        build_cva_netting_set_batch_from_netting_sets(
            netting_set_rows,
            counterparties=counterparty_rows,
        )
        if netting_set_rows
        else None,
        hedges=build_cva_hedge_batch_from_hedges(hedge_rows) if hedge_rows else None,
        sensitivities=build_sa_cva_sensitivity_batch_from_sensitivities(sensitivity_rows)
        if sensitivity_rows
        else None,
    )


def _assert_result_parity(row_result: CvaCapitalResult, batch_result: CvaCapitalResult) -> None:
    validate_cva_result_reconciliation(row_result)
    validate_cva_result_reconciliation(batch_result)
    assert batch_result.method is row_result.method
    assert batch_result.total_cva_capital == pytest.approx(row_result.total_cva_capital)
    assert batch_result.citations
    assert batch_result.citations == row_result.citations
    assert len(batch_result.method_components) == len(row_result.method_components)
    for row_component, batch_component in zip(
        row_result.method_components,
        batch_result.method_components,
        strict=True,
    ):
        assert batch_component.method is row_component.method
        assert batch_component.total_capital == pytest.approx(row_component.total_capital)
        assert batch_component.citations == row_component.citations


def _sensitivity(
    sensitivity_id: str,
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    bucket_id: str,
    risk_factor_key: str,
    *,
    amount: float = 1_000_000.0,
    **overrides: object,
) -> SaCvaSensitivity:
    base = dict(
        sensitivity_id=sensitivity_id,
        risk_class=risk_class,
        risk_measure=risk_measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket_id,
        risk_factor_key=risk_factor_key,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-{sensitivity_id.removeprefix('sens-')}",
        lineage=_lineage("sensitivities.csv", f"row-{sensitivity_id.removeprefix('sens-')}"),
    )
    base.update(overrides)
    return SaCvaSensitivity(**base)  # type: ignore[arg-type]


def _supported_sa_cva_sensitivities() -> tuple[SaCvaSensitivity, ...]:
    risk = SaCvaRiskClass
    measure = SaCvaRiskMeasure
    vega_amount = 500_000.0
    return (
        _sensitivity("sens-girr-delta", risk.GIRR, measure.DELTA, "USD", "5y", tenor="5y"),
        _sensitivity(
            "sens-girr-vega",
            risk.GIRR,
            measure.VEGA,
            "USD",
            GIRR_VEGA_RATE_FACTOR,
            amount=vega_amount,
            volatility_input=0.2,
        ),
        _sensitivity("sens-fx-delta", risk.FX, measure.DELTA, "EUR", "SPOT"),
        _sensitivity(
            "sens-fx-vega",
            risk.FX,
            measure.VEGA,
            "EUR",
            "SPOT",
            amount=vega_amount,
            volatility_input=0.2,
        ),
        _sensitivity(
            "sens-ccs-index",
            risk.COUNTERPARTY_CREDIT_SPREAD,
            measure.DELTA,
            "8",
            "INDEX|INVESTMENT_GRADE",
            tenor="5y",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
            index_homogeneous_sector_quality=True,
        ),
        _sensitivity(
            "sens-rcs-index",
            risk.REFERENCE_CREDIT_SPREAD,
            measure.DELTA,
            "16",
            "INDEX",
            tenor="5y",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        ),
        _sensitivity(
            "sens-rcs-vega",
            risk.REFERENCE_CREDIT_SPREAD,
            measure.VEGA,
            "1",
            "1y",
            amount=vega_amount,
            volatility_input=0.3,
        ),
        _sensitivity(
            "sens-equity-index",
            risk.EQUITY,
            measure.DELTA,
            "12",
            "INDEX",
            tenor="5y",
            index_treatment=SaCvaIndexTreatment.QUALIFIED_INDEX,
        ),
        _sensitivity(
            "sens-equity-vega",
            risk.EQUITY,
            measure.VEGA,
            "1",
            "SPOT",
            amount=vega_amount,
            volatility_input=0.3,
        ),
        _sensitivity(
            "sens-commodity-delta",
            risk.COMMODITY,
            measure.DELTA,
            "1",
            "OIL",
        ),
        _sensitivity(
            "sens-commodity-vega",
            risk.COMMODITY,
            measure.VEGA,
            "1",
            "OIL",
            amount=vega_amount,
            volatility_input=0.3,
        ),
    )


def test_ba_cva_reduced_row_and_batch_characterization() -> None:
    counterparties = _counterparties()
    netting_sets = _netting_sets()
    context = _context(CvaMethod.BA_CVA_REDUCED, "run-ba-reduced")

    row_result = calculate_cva_capital(context, counterparties, netting_sets)
    batch_result = _batch_result(context, counterparties, netting_sets).result

    _assert_result_parity(row_result, batch_result)
    assert row_result.ba_cva_reduced is not None
    assert batch_result.ba_cva_reduced is not None
    assert {line.netting_set_id for line in batch_result.ba_cva_netting_set_lines} == {
        "ns-sovereign",
        "ns-financial",
    }
    assert {item.counterparty_id for item in batch_result.ba_cva_counterparty_capitals} == {
        "cp-sovereign",
        "cp-financial",
    }
    assert all(line.citations for line in batch_result.ba_cva_netting_set_lines)
    assert all(item.citations for item in batch_result.ba_cva_counterparty_capitals)


def test_ba_cva_full_row_and_batch_characterization() -> None:
    counterparties = _counterparties()
    netting_sets = _netting_sets()
    hedges = _ba_hedges()
    context = _context(CvaMethod.BA_CVA_FULL, "run-ba-full")

    row_result = calculate_cva_capital(context, counterparties, netting_sets, hedges=hedges)
    batch_result = _batch_result(context, counterparties, netting_sets, hedges=hedges).result

    _assert_result_parity(row_result, batch_result)
    assert batch_result.ba_cva_full is not None
    hedge_lines = {line.hedge_id: line for line in batch_result.ba_cva_full.hedge_lines}
    assert set(hedge_lines) == {"h-single-name", "h-index", "h-ineligible"}
    assert hedge_lines["h-single-name"].snh_contribution > 0.0
    assert hedge_lines["h-index"].index_contribution > 0.0
    assert hedge_lines["h-ineligible"].reason_code == "tranched_credit_derivative"
    assert hedge_lines["h-ineligible"].snh_contribution == 0.0
    assert all(line.citations for line in hedge_lines.values())
    assert {item[0] for item in batch_result.ba_cva_full.counterparty_adjusted_standalone} == {
        "cp-sovereign",
        "cp-financial",
    }


def test_sa_cva_supported_paths_row_and_batch_characterization() -> None:
    sensitivities = _supported_sa_cva_sensitivities()
    context = _context(CvaMethod.SA_CVA, "run-sa-cva", sa_cva_approved=True)

    row_result = calculate_cva_capital(context, (), (), sensitivities=sensitivities)
    batch_result = _batch_result(context, sensitivities=sensitivities).result

    _assert_result_parity(row_result, batch_result)
    expected_paths = {
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA),
    }
    actual_paths = {
        (item.risk_class, item.risk_measure) for item in batch_result.sa_cva_risk_class_capitals
    }
    assert actual_paths == expected_paths

    bucket_by_source_id = {
        sensitivity_id: bucket
        for item in batch_result.sa_cva_risk_class_capitals
        for bucket in item.bucket_capitals
        for sensitivity_id in bucket.sensitivity_ids
    }
    assert bucket_by_source_id["sens-ccs-index"].bucket_id == "8"
    assert bucket_by_source_id["sens-rcs-index"].bucket_id == "16"
    assert bucket_by_source_id["sens-equity-index"].bucket_id == "12"
    assert all(item.citations for item in batch_result.sa_cva_risk_class_capitals)
    assert all(
        bucket.citations
        for item in batch_result.sa_cva_risk_class_capitals
        for bucket in item.bucket_capitals
    )


def test_mixed_carve_out_row_and_batch_characterization() -> None:
    counterparties = _counterparties()
    netting_sets = _netting_sets(carve_out_sovereign=True)
    sensitivities = (_supported_sa_cva_sensitivities()[0],)
    context = _context(
        CvaMethod.MIXED_CARVE_OUT,
        "run-mixed",
        sa_cva_approved=True,
        carve_out_netting_set_ids=("ns-sovereign",),
        sa_cva_sensitivity_scope_evidence_id="sa-scope-ledger-2026-06-10",
    )

    row_result = calculate_cva_capital(
        context,
        counterparties,
        netting_sets,
        sensitivities=sensitivities,
    )
    batch_result = _batch_result(
        context,
        counterparties,
        netting_sets,
        sensitivities=sensitivities,
    ).result

    _assert_result_parity(row_result, batch_result)
    assert dict(batch_result.audit_metadata)["sa_cva_sensitivity_scope_evidence_id"] == (
        "sa-scope-ledger-2026-06-10"
    )
    assert {component.method for component in batch_result.method_components} == {
        CvaMethod.SA_CVA,
        CvaMethod.BA_CVA_REDUCED,
    }
    assert {line.netting_set_id for line in batch_result.ba_cva_netting_set_lines} == {
        "ns-sovereign"
    }


@pytest.mark.parametrize(
    ("context", "error_match"),
    (
        (
            _context(
                CvaMethod.MIXED_CARVE_OUT,
                "run-mixed-missing-evidence",
                sa_cva_approved=True,
                carve_out_netting_set_ids=("ns-sovereign",),
            ),
            "sensitivity scope evidence",
        ),
        (
            _context(
                CvaMethod.MIXED_CARVE_OUT,
                "run-mixed-missing-id",
                sa_cva_approved=True,
                carve_out_netting_set_ids=("ns-missing",),
                sa_cva_sensitivity_scope_evidence_id="sa-scope-ledger-2026-06-10",
            ),
            "carve_out_netting_set_ids",
        ),
    ),
)
def test_mixed_carve_out_fail_closed_row_and_batch(
    context: CvaCalculationContext,
    error_match: str,
) -> None:
    counterparties = _counterparties()
    netting_sets = _netting_sets(carve_out_sovereign=True)
    sensitivities = (_supported_sa_cva_sensitivities()[0],)

    with pytest.raises(CvaInputError, match=error_match):
        calculate_cva_capital(context, counterparties, netting_sets, sensitivities=sensitivities)

    with pytest.raises(CvaInputError, match=error_match):
        _batch_result(context, counterparties, netting_sets, sensitivities=sensitivities)


def test_sa_cva_ccs_vega_remains_fail_closed_for_row_and_batch() -> None:
    sensitivity = replace(
        _supported_sa_cva_sensitivities()[4],
        sensitivity_id="sens-ccs-vega",
        risk_measure=SaCvaRiskMeasure.VEGA,
        source_row_id="row-ccs-vega",
        volatility_input=0.2,
    )
    context = _context(CvaMethod.SA_CVA, "run-sa-cva-unsupported", sa_cva_approved=True)

    with pytest.raises(CvaInputError, match="CCS vega capital is not permitted"):
        calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))

    with pytest.raises(CvaInputError, match="CCS vega capital is not permitted"):
        _batch_result(context, sensitivities=(sensitivity,))


def test_qualified_index_look_through_remains_fail_closed_for_row_and_batch() -> None:
    sensitivity = replace(
        _supported_sa_cva_sensitivities()[4],
        index_treatment=SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED,
        bucket_id="2",
    )
    context = _context(CvaMethod.SA_CVA, "run-sa-cva-look-through", sa_cva_approved=True)

    with pytest.raises(CvaInputError, match="look-through"):
        calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))

    with pytest.raises(CvaInputError, match="look-through"):
        _batch_result(context, sensitivities=(sensitivity,))
