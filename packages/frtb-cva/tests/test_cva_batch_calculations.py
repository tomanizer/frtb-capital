from __future__ import annotations

import unittest.mock as mock
from datetime import date

import numpy as np
import pyarrow as pa
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
    HedgeEligibility,
    HedgeReferenceRelation,
    build_cva_counterparty_batch_from_arrow,
    build_cva_counterparty_batch_from_columns,
    build_cva_hedge_batch_from_arrow,
    build_cva_hedge_batch_from_columns,
    build_cva_netting_set_batch_from_arrow,
    build_cva_netting_set_batch_from_columns,
    build_sa_cva_sensitivity_batch_from_arrow,
    build_sa_cva_sensitivity_batch_from_columns,
    calculate_cva_capital_from_batches,
    calculate_full_portfolio,
    calculate_reduced_portfolio,
    normalize_cva_netting_set_arrow_table,
)
from frtb_cva._batch_validation import _validate_netting_set_batch
from frtb_cva._sa_batch_kernel import calculate_sa_cva_capital_from_batch
from frtb_cva.audit import validate_cva_result_reconciliation
from frtb_cva.batch import CvaNettingSetBatch, SaCvaSensitivityBatch


def test_full_portfolio_with_hedges_batch() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
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
        lineage_source_systems=["synthetic"],
        lineage_source_files=["netting-sets.csv"],
    )

    hedge_batch = build_cva_hedge_batch_from_columns(
        hedge_ids=["h-1", "h-2", "h-3", "h-4"],
        source_row_ids=["h-row-1", "h-row-2", "h-row-3", "h-row-4"],
        counterparty_ids=["cp-1", "cp-1", "cp-1", "cp-1"],
        hedge_types=["SINGLE_NAME_CDS", "INDEX_CDS", "SINGLE_NAME_CDS", "SINGLE_NAME_CDS"],
        notionals=[50_000.0, 100_000.0, 40_000.0, 30_000.0],
        remaining_maturities=[2.0, 3.0, 1.5, 2.5],
        discount_factors=[0.99, 0.98, 0.95, 0.97],
        reference_sectors=["SOVEREIGN", "FINANCIALS", "SOVEREIGN", "SOVEREIGN"],
        reference_credit_qualities=[
            "INVESTMENT_GRADE",
            "INVESTMENT_GRADE",
            "INVESTMENT_GRADE",
            "INVESTMENT_GRADE",
        ],
        reference_regions=["EMEA", "EMEA", "EMEA", "EMEA"],
        reference_relations=[
            "DIRECT",
            "SAME_SECTOR_AND_REGION",
            "LEGAL_RELATION",
            "SAME_SECTOR_AND_REGION",
        ],
        eligibilities=["ELIGIBLE", "ELIGIBLE", "ELIGIBLE", "ELIGIBLE"],
        is_internal=[False, False, False, False],
        eligibility_evidence_ids=["ev-1", "ev-2", "ev-3", "ev-4"],
        lineage_source_systems=["synthetic", "synthetic", "synthetic", "synthetic"],
        lineage_source_files=["hedges.csv", "hedges.csv", "hedges.csv", "hedges.csv"],
    )

    context = CvaCalculationContext(
        run_id="run-full",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_FULL,
        sa_cva_approved=False,
    )

    calc = calculate_cva_capital_from_batches(
        context,
        counterparty_batch,
        netting_set_batch,
        hedges=hedge_batch,
    )
    assert calc.result.total_cva_capital > 0.0
    assert len(calc.result.ba_cva_full.hedge_lines) == 4

    # Verify audit verification does not crash
    validate_cva_result_reconciliation(calc.result)


def test_mixed_carve_out_batch() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
        counterparty_ids=["cp-1", "cp-2"],
        desk_ids=["desk-1", "desk-1"],
        legal_entities=["LE-001", "LE-001"],
        sectors=["SOVEREIGN", "FINANCIALS"],
        credit_qualities=["INVESTMENT_GRADE", "INVESTMENT_GRADE"],
        regions=["EMEA", "EMEA"],
        source_row_ids=["cp-row-1", "cp-row-2"],
        lineage_source_systems=["synthetic", "synthetic"],
        lineage_source_files=["counterparties.csv", "counterparties.csv"],
    )

    netting_set_batch = build_cva_netting_set_batch_from_columns(
        netting_set_ids=["ns-1", "ns-2"],
        counterparty_ids=["cp-1", "cp-2"],
        eads=[100_000.0, 200_000.0],
        effective_maturities=[2.5, 1.5],
        discount_factors=[0.98, 0.99],
        currencies=["USD", "USD"],
        sign_conventions=["non_negative", "non_negative"],
        uses_imm_eads=[False, False],
        carved_out_to_ba_cva=[True, False],
        source_row_ids=["ns-row-1", "ns-row-2"],
        lineage_source_systems=["synthetic", "synthetic"],
        lineage_source_files=["netting-sets.csv", "netting-sets.csv"],
    )

    sens_batch = build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-1"],
        risk_classes=["GIRR"],
        risk_measures=["DELTA"],
        sensitivity_tags=["CVA"],
        bucket_ids=["USD"],
        risk_factor_keys=["5y"],
        amounts=[1000.0],
        amount_currencies=["USD"],
        sign_conventions=["positive_loss"],
        source_row_ids=["sens-row-1"],
        tenors=["5y"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["sens.csv"],
    )

    context = CvaCalculationContext(
        run_id="run-mixed",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=("ns-1",),
        sa_cva_sensitivity_scope_evidence_id="sa-slice-non-carved-ledger-2026-06-01",
    )

    calc = calculate_cva_capital_from_batches(
        context,
        counterparty_batch,
        netting_set_batch,
        sensitivities=sens_batch,
    )
    assert calc.result.total_cva_capital > 0.0
    assert (
        "sa_cva_sensitivity_scope_evidence_id",
        "sa-slice-non-carved-ledger-2026-06-01",
    ) in calc.result.audit_metadata
    assert calc.result.ba_cva_reduced is not None
    assert {line.netting_set_id for line in calc.result.ba_cva_reduced.netting_set_lines} == {
        "ns-1"
    }
    validate_cva_result_reconciliation(calc.result)


def test_mixed_carve_out_batch_rejects_unaudited_sa_sensitivity_scope() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
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

    netting_set_batch = build_cva_netting_set_batch_from_columns(
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
        lineage_source_systems=["synthetic"],
        lineage_source_files=["netting-sets.csv"],
    )

    sens_batch = build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-1"],
        risk_classes=["GIRR"],
        risk_measures=["DELTA"],
        sensitivity_tags=["CVA"],
        bucket_ids=["USD"],
        risk_factor_keys=["5y"],
        amounts=[1000.0],
        amount_currencies=["USD"],
        sign_conventions=["positive_loss"],
        source_row_ids=["sens-row-1"],
        tenors=["5y"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["sens.csv"],
    )

    context = CvaCalculationContext(
        run_id="run-mixed-double-count",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=("ns-1",),
    )

    with pytest.raises(CvaInputError, match="sensitivity scope evidence"):
        calculate_cva_capital_from_batches(
            context,
            counterparty_batch,
            netting_set_batch,
            sensitivities=sens_batch,
        )


def test_mixed_carve_out_missing_sensitivities() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
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
    netting_set_batch = build_cva_netting_set_batch_from_columns(
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
        lineage_source_systems=["synthetic"],
        lineage_source_files=["netting-sets.csv"],
    )
    context = CvaCalculationContext(
        run_id="run-mixed-fail",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=("ns-1",),
        sa_cva_sensitivity_scope_evidence_id="missing-sensitivity-scope-evidence",
    )
    with pytest.raises(CvaInputError, match="mixed carve-out requires SA-CVA sensitivities"):
        calculate_cva_capital_from_batches(
            context, counterparty_batch, netting_set_batch, sensitivities=None
        )


def test_sa_cva_method_with_unsupported_inputs() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
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
    context = CvaCalculationContext(
        run_id="run-sa-fail",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    with pytest.raises(
        CvaInputError, match="SA-CVA does not accept counterparty or netting-set inputs"
    ):
        calculate_cva_capital_from_batches(
            context, counterparties=counterparty_batch, sensitivities=None
        )


def test_sa_cva_method_missing_sensitivities() -> None:
    context = CvaCalculationContext(
        run_id="run-sa-fail-2",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    with pytest.raises(CvaInputError, match="SA-CVA requires sensitivities"):
        calculate_cva_capital_from_batches(context, sensitivities=None)


def test_reduced_portfolio_zero_counterparties() -> None:
    # Call via calculate_reduced_portfolio with empty arrays
    with pytest.raises(CvaInputError, match="at least one counterparty is required"):
        calculate_reduced_portfolio((), ())


def test_standalone_capital_finite_check() -> None:
    # Test finite float exception in reduced portfolio standalone sum
    counterparties = build_cva_counterparty_batch_from_columns(
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
    netting_sets = build_cva_netting_set_batch_from_columns(
        netting_set_ids=["ns-1"],
        counterparty_ids=["cp-1"],
        eads=[100_000.0],
        effective_maturities=[2.5],
        discount_factors=[0.98],
        currencies=["USD"],
        sign_conventions=["non_negative"],
        uses_imm_eads=[False],
        source_row_ids=["ns-row-1"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["netting-sets.csv"],
    )
    with mock.patch("frtb_cva._ba_reduced_batch_kernel.math.isfinite", return_value=False):
        with pytest.raises(CvaInputError, match="standalone capital must be finite"):
            calculate_cva_capital_from_batches(
                CvaCalculationContext(
                    run_id="run-inf",
                    calculation_date=date(2026, 6, 1),
                    base_currency="USD",
                    profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
                    method=CvaMethod.BA_CVA_REDUCED,
                ),
                counterparties,
                netting_sets,
            )


def test_full_portfolio_hedge_counterparty_mismatch() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
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
        lineage_source_systems=["synthetic"],
        lineage_source_files=["netting-sets.csv"],
    )
    hedge_batch = build_cva_hedge_batch_from_columns(
        hedge_ids=["h-1"],
        source_row_ids=["h-row-1"],
        counterparty_ids=["cp-missing"],  # Mismatched counterparty
        hedge_types=["SINGLE_NAME_CDS"],
        notionals=[50_000.0],
        remaining_maturities=[2.0],
        discount_factors=[0.99],
        reference_sectors=["SOVEREIGN"],
        reference_credit_qualities=["INVESTMENT_GRADE"],
        reference_regions=["EMEA"],
        reference_relations=["DIRECT"],
        eligibilities=["ELIGIBLE"],
        is_internal=[False],
        eligibility_evidence_ids=["ev-1"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["hedges.csv"],
    )
    with pytest.raises(CvaInputError, match="hedge counterparty is not in BA-CVA counterparty set"):
        calculate_cva_capital_from_batches(
            CvaCalculationContext(
                run_id="run-mismatch",
                calculation_date=date(2026, 6, 1),
                base_currency="USD",
                profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
                method=CvaMethod.BA_CVA_FULL,
            ),
            counterparty_batch,
            netting_set_batch,
            hedges=hedge_batch,
        )


def test_full_portfolio_ineligible_unknown_counterparty_hedge_has_zero_benefit() -> None:
    counterparty_batch = build_cva_counterparty_batch_from_columns(
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
        lineage_source_systems=["synthetic"],
        lineage_source_files=["netting-sets.csv"],
    )
    hedge_batch = build_cva_hedge_batch_from_columns(
        hedge_ids=["h-1"],
        source_row_ids=["h-row-1"],
        counterparty_ids=["cp-missing"],
        hedge_types=["SINGLE_NAME_CDS"],
        notionals=[50_000.0],
        remaining_maturities=[2.0],
        discount_factors=[0.99],
        reference_sectors=["SOVEREIGN"],
        reference_credit_qualities=["INVESTMENT_GRADE"],
        reference_regions=["EMEA"],
        reference_relations=["DIRECT"],
        eligibilities=["INELIGIBLE"],
        is_internal=[False],
        rejection_reasons=["hedge_marked_ineligible"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["hedges.csv"],
    )

    calculation = calculate_cva_capital_from_batches(
        CvaCalculationContext(
            run_id="run-ineligible-missing",
            calculation_date=date(2026, 6, 1),
            base_currency="USD",
            profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
            method=CvaMethod.BA_CVA_FULL,
        ),
        counterparty_batch,
        netting_set_batch,
        hedges=hedge_batch,
    )

    full = calculation.result.ba_cva_full
    assert full is not None
    assert full.hedge_lines[0].counterparty_id == "cp-missing"
    assert full.hedge_lines[0].snh_contribution == 0.0
    assert full.hedge_lines[0].hma_contribution == 0.0
    assert full.counterparty_adjusted_standalone == (
        ("cp-1", full.reduced.counterparty_capitals[0].standalone_capital),
    )


def test_sa_cva_capital_batch_zero_sensitivities() -> None:
    empty_batch = SaCvaSensitivityBatch(
        sensitivity_ids=np.empty(0, dtype=object),
        risk_classes=np.empty(0, dtype=object),
        risk_measures=np.empty(0, dtype=object),
        sensitivity_tags=np.empty(0, dtype=object),
        bucket_ids=np.empty(0, dtype=object),
        risk_factor_keys=np.empty(0, dtype=object),
        amounts=np.empty(0, dtype=np.float64),
        amount_currencies=np.empty(0, dtype=object),
        sign_conventions=np.empty(0, dtype=object),
        source_row_ids=np.empty(0, dtype=object),
        tenors=np.empty(0, dtype=object),
        volatility_inputs=np.empty(0, dtype=np.float64),
        hedge_ids=np.empty(0, dtype=object),
        index_treatments=np.empty(0, dtype=object),
        index_max_sector_weights=np.empty(0, dtype=np.float64),
        index_homogeneous_sector_quality=np.empty(0, dtype=np.bool_),
        index_dominant_sectors=np.empty(0, dtype=object),
        index_remap_bucket_ids=np.empty(0, dtype=object),
        lineage_source_systems=np.empty(0, dtype=object),
        lineage_source_files=np.empty(0, dtype=object),
        lineage_source_row_ids=np.empty(0, dtype=object),
        source_column_maps=(),
    )
    with pytest.raises(CvaInputError, match="SA-CVA requires at least one sensitivity"):
        calculate_cva_capital_from_batches(
            CvaCalculationContext(
                run_id="run-sa-zero",
                calculation_date=date(2026, 6, 1),
                base_currency="USD",
                profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
                method=CvaMethod.SA_CVA,
                sa_cva_approved=True,
            ),
            sensitivities=empty_batch,
        )


def test_batch_validation_negative_ead_normalise() -> None:
    # Explicitly check validation errors by calling validators directly
    # Negative EAD with signed_absolute sign convention that hasn't been normalised
    batch = CvaNettingSetBatch(
        netting_set_ids=np.array(["ns-1"]),
        counterparty_ids=np.array(["cp-1"]),
        eads=np.array([-1000.0]),  # Negative EAD
        effective_maturities=np.array([1.5]),
        discount_factors=np.array([1.0]),
        currencies=np.array(["USD"]),
        sign_conventions=np.array(["signed_absolute"]),
        uses_imm_eads=np.array([False]),
        source_row_ids=np.array(["row-1"]),
        carved_out_to_ba_cva=np.array([False]),
        discount_factor_explicit=np.array([False]),
        lineage_source_systems=np.array(["sys"]),
        lineage_source_files=np.array(["file"]),
        lineage_source_row_ids=np.array(["row-1"]),
        source_column_maps=(),
        source_hash=None,
        handoff_hash=None,
        diagnostics=(),
    )
    with pytest.raises(
        CvaInputError, match="EAD must be stored after sign-convention normalisation"
    ):
        _validate_netting_set_batch(batch)


def test_batch_validation_negative_effective_maturity() -> None:
    batch = CvaNettingSetBatch(
        netting_set_ids=np.array(["ns-1"]),
        counterparty_ids=np.array(["cp-1"]),
        eads=np.array([1000.0]),
        effective_maturities=np.array([-1.5]),  # Negative maturity
        discount_factors=np.array([1.0]),
        currencies=np.array(["USD"]),
        sign_conventions=np.array(["non_negative"]),
        uses_imm_eads=np.array([False]),
        source_row_ids=np.array(["row-1"]),
        carved_out_to_ba_cva=np.array([False]),
        discount_factor_explicit=np.array([False]),
        lineage_source_systems=np.array(["sys"]),
        lineage_source_files=np.array(["file"]),
        lineage_source_row_ids=np.array(["row-1"]),
        source_column_maps=(),
        source_hash=None,
        handoff_hash=None,
        diagnostics=(),
    )
    with pytest.raises(CvaInputError, match="effective maturity must be non-negative"):
        _validate_netting_set_batch(batch)


def test_batch_validation_invalid_discount_factor() -> None:
    batch = CvaNettingSetBatch(
        netting_set_ids=np.array(["ns-1"]),
        counterparty_ids=np.array(["cp-1"]),
        eads=np.array([1000.0]),
        effective_maturities=np.array([1.5]),
        discount_factors=np.array([0.0]),  # Non-positive discount factor
        currencies=np.array(["USD"]),
        sign_conventions=np.array(["non_negative"]),
        uses_imm_eads=np.array([False]),
        source_row_ids=np.array(["row-1"]),
        carved_out_to_ba_cva=np.array([False]),
        discount_factor_explicit=np.array([False]),
        lineage_source_systems=np.array(["sys"]),
        lineage_source_files=np.array(["file"]),
        lineage_source_row_ids=np.array(["row-1"]),
        source_column_maps=(),
        source_hash=None,
        handoff_hash=None,
        diagnostics=(),
    )
    with pytest.raises(CvaInputError, match="discount factor must be positive"):
        _validate_netting_set_batch(batch)


def test_sa_cva_vega_weight_batch() -> None:
    # Trigger vega aggregation path in batch execution: _weight_girr_vega
    sens_batch = build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-1", "sens-2"],
        risk_classes=["GIRR", "GIRR"],
        risk_measures=["VEGA", "VEGA"],
        sensitivity_tags=["CVA", "HDG"],
        bucket_ids=["USD", "USD"],
        risk_factor_keys=["IR_VOL", "IR_VOL"],
        amounts=[1000.0, 500.0],
        amount_currencies=["USD", "USD"],
        sign_conventions=["positive_loss", "positive_loss"],
        source_row_ids=["sens-row-1", "sens-row-2"],
        tenors=["5y", "5y"],
        volatility_inputs=[0.2, 0.2],
        hedge_ids=[None, "h-1"],
        lineage_source_systems=["synthetic", "synthetic"],
        lineage_source_files=["sens.csv", "sens.csv"],
    )

    hedge_batch = build_cva_hedge_batch_from_columns(
        hedge_ids=["h-1"],
        source_row_ids=["h-row-1"],
        counterparty_ids=["cp-1"],
        hedge_types=["SINGLE_NAME_CDS"],
        notionals=[200_000.0],
        remaining_maturities=[5.0],
        discount_factors=[1.0],
        reference_sectors=["SOVEREIGN"],
        reference_credit_qualities=["INVESTMENT_GRADE"],
        reference_regions=["EMEA"],
        reference_relations=["DIRECT"],
        eligibilities=["ELIGIBLE"],
        is_internal=[False],
        eligibility_evidence_ids=["evidence-1"],
        sa_cva_risk_classes=["GIRR"],  # Eligible for GIRR
        sa_cva_hedge_purposes=["EXPOSURE_COMPONENT"],
        sa_cva_hedge_instrument_types=["INTEREST_RATE"],
        whole_transaction_evidence_ids=["whole-transaction-1"],
        market_risk_ima_eligibilities=[True],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["hedges.csv"],
    )

    context = CvaCalculationContext(
        run_id="run-sa-vega",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )

    calc = calculate_cva_capital_from_batches(
        context,
        sensitivities=sens_batch,
        hedges=hedge_batch,
    )
    assert calc.result.total_cva_capital > 0.0


def test_sa_cva_batch_exposure_component_hedge_without_ba_type_offsets_hdg() -> None:
    sens_batch = build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-cva", "sens-hdg"],
        risk_classes=["GIRR", "GIRR"],
        risk_measures=["DELTA", "DELTA"],
        sensitivity_tags=["CVA", "HDG"],
        bucket_ids=["USD", "USD"],
        risk_factor_keys=["5y", "5y"],
        amounts=[1000.0, 250.0],
        amount_currencies=["USD", "USD"],
        sign_conventions=["positive_loss", "positive_loss"],
        source_row_ids=["sens-row-cva", "sens-row-hdg"],
        tenors=["5y", "5y"],
        hedge_ids=[None, "h-exposure"],
        lineage_source_systems=["synthetic", "synthetic"],
        lineage_source_files=["sens.csv", "sens.csv"],
    )
    hedge_batch = build_cva_hedge_batch_from_columns(
        hedge_ids=["h-exposure"],
        source_row_ids=["h-row-exposure"],
        counterparty_ids=["cp-1"],
        hedge_types=[None],
        notionals=[200_000.0],
        remaining_maturities=[5.0],
        discount_factors=[1.0],
        reference_sectors=["SOVEREIGN"],
        reference_credit_qualities=["INVESTMENT_GRADE"],
        reference_regions=["EMEA"],
        reference_relations=["DIRECT"],
        eligibilities=["ELIGIBLE"],
        is_internal=[False],
        eligibility_evidence_ids=["evidence-1"],
        sa_cva_risk_classes=["GIRR"],
        sa_cva_hedge_purposes=["EXPOSURE_COMPONENT"],
        sa_cva_hedge_instrument_types=["INTEREST_RATE"],
        whole_transaction_evidence_ids=["whole-transaction-1"],
        market_risk_ima_eligibilities=[True],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["hedges.csv"],
    )

    unhedged = calculate_sa_cva_capital_from_batch(
        build_sa_cva_sensitivity_batch_from_columns(
            sensitivity_ids=["sens-cva"],
            risk_classes=["GIRR"],
            risk_measures=["DELTA"],
            sensitivity_tags=["CVA"],
            bucket_ids=["USD"],
            risk_factor_keys=["5y"],
            amounts=[1000.0],
            amount_currencies=["USD"],
            sign_conventions=["positive_loss"],
            source_row_ids=["sens-row-cva"],
            tenors=["5y"],
            lineage_source_systems=["synthetic"],
            lineage_source_files=["sens.csv"],
        )
    )
    hedged = calculate_sa_cva_capital_from_batch(sens_batch, hedges=hedge_batch)
    assert hedged[0].post_multiplier_capital < unhedged[0].post_multiplier_capital


def test_sa_cva_conflicting_volatility_inputs() -> None:
    sens_batch = build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-1", "sens-2"],
        risk_classes=["GIRR", "GIRR"],
        risk_measures=["VEGA", "VEGA"],
        sensitivity_tags=["CVA", "CVA"],
        bucket_ids=["USD", "USD"],
        risk_factor_keys=["IR_VOL", "IR_VOL"],
        amounts=[1000.0, 500.0],
        amount_currencies=["USD", "USD"],
        sign_conventions=["positive_loss", "positive_loss"],
        source_row_ids=["sens-row-1", "sens-row-2"],
        tenors=["5y", "5y"],
        volatility_inputs=[0.2, 0.4],  # Conflicting volatility inputs!
        hedge_ids=[None, None],
        lineage_source_systems=["synthetic", "synthetic"],
        lineage_source_files=["sens.csv", "sens.csv"],
    )
    context = CvaCalculationContext(
        run_id="run-conflicting-vol",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    with pytest.raises(CvaInputError, match="conflicting volatility_input"):
        calculate_cva_capital_from_batches(context, sensitivities=sens_batch)


def test_sa_cva_no_eligible_sensitivities() -> None:
    # All are HDG sensitivities but no eligible hedges are provided
    sens_batch = build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=["sens-1"],
        risk_classes=["GIRR"],
        risk_measures=["DELTA"],
        sensitivity_tags=["HDG"],  # tag HDG but no eligible hedges
        bucket_ids=["USD"],
        risk_factor_keys=["5y"],
        amounts=[1000.0],
        amount_currencies=["USD"],
        sign_conventions=["positive_loss"],
        source_row_ids=["sens-row-1"],
        tenors=["5y"],
        hedge_ids=["h-missing"],
        lineage_source_systems=["synthetic"],
        lineage_source_files=["sens.csv"],
    )
    context = CvaCalculationContext(
        run_id="run-no-eligible",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    with pytest.raises(CvaInputError, match="SA-CVA path has no eligible sensitivities"):
        calculate_cva_capital_from_batches(context, sensitivities=sens_batch)


def test_arrow_batch_wrong_instance_rejections() -> None:
    with pytest.raises(CvaInputError, match="handoff must be NormalizedArrowTable"):
        build_cva_counterparty_batch_from_arrow(object())  # type: ignore[arg-type]
    with pytest.raises(CvaInputError, match="handoff must be NormalizedArrowTable"):
        build_cva_netting_set_batch_from_arrow(object())  # type: ignore[arg-type]
    with pytest.raises(CvaInputError, match="handoff must be NormalizedArrowTable"):
        build_cva_hedge_batch_from_arrow(object())  # type: ignore[arg-type]
    with pytest.raises(CvaInputError, match="handoff must be NormalizedArrowTable"):
        build_sa_cva_sensitivity_batch_from_arrow(object())  # type: ignore[arg-type]


def test_arrow_batch_chunked_dictionary_and_arrays() -> None:
    # Test booleans chunked/non-boolean columns logic in arrow_batch.py
    # and dictionary columns, missing required columns etc.
    table = pa.table(
        {
            "netting_set_id": ["ns-1"],
            "counterparty_id": ["cp-1"],
            "ead": ["100000.0"],  # string representation of float for testing cast
            "effective_maturity": ["2.5"],
            "discount_factor": ["0.95"],
            "currency": ["USD"],
            "sign_convention": ["non_negative"],
            # uses_imm_ead is boolean: pass it as a chunked array
            "uses_imm_ead": [False],
            "source_row_id": ["row-1"],
            "lineage_source_system": ["sys"],
            "lineage_source_file": ["file"],
        }
    )
    handoff = normalize_cva_netting_set_arrow_table(table)
    batch = build_cva_netting_set_batch_from_arrow(handoff)
    assert batch.eads[0] == 100000.0

    # Test dictionary / integer array conversions in arrow_batch.py
    # We will test booleans as string column (not standard boolean) to trigger
    # fallback in _bool_array_from_arrow_column
    bad_bool_table = pa.table(
        {
            "netting_set_id": ["ns-1"],
            "counterparty_id": ["cp-1"],
            "ead": [100000.0],
            "effective_maturity": [2.5],
            "discount_factor": [0.95],
            "currency": ["USD"],
            "sign_convention": ["non_negative"],
            "uses_imm_ead": ["False"],  # String instead of boolean!
            "source_row_id": ["row-1"],
            "lineage_source_system": ["sys"],
            "lineage_source_file": ["file"],
        }
    )
    rejected_table = pa.table({"netting_set_id": ["ns-bad"]})
    handoff_bad = normalize_cva_netting_set_arrow_table(bad_bool_table, rejected=rejected_table)
    assert handoff_bad.rejected is rejected_table
    assert len(handoff_bad.rejected) == 1

    batch_bad = build_cva_netting_set_batch_from_arrow(handoff_bad)
    assert not batch_bad.uses_imm_eads[0]


def test_ba_cva_dataclass_full_portfolio_index_cds() -> None:
    # Reconcile index CDS hedges logic in dataclass portfolio path: calculate_full_portfolio
    cp = CvaCounterparty(
        counterparty_id="cp-1",
        desk_id="desk-1",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="cp-row-1",
    )
    ns = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id="cp-1",
        ead=100_000.0,
        effective_maturity=2.5,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="ns-row-1",
    )
    # Single-name hedge with same sector and region (triggers HMA)
    hedge_sn_hma = CvaHedge(
        hedge_id="h-sn-hma",
        source_row_id="h-row-1",
        counterparty_id="cp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=50_000.0,
        remaining_maturity=2.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.SAME_SECTOR_AND_REGION,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-1",
    )
    # Index hedge
    hedge_idx = CvaHedge(
        hedge_id="h-idx",
        source_row_id="h-row-2",
        counterparty_id="cp-1",
        hedge_type=BaCvaHedgeType.INDEX_CDS,
        notional=100_000.0,
        remaining_maturity=3.0,
        discount_factor=1.0,
        reference_sector=CvaSector.FINANCIALS,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.SAME_SECTOR_AND_REGION,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-2",
    )

    full_result = calculate_full_portfolio((cp,), (ns,), (hedge_sn_hma, hedge_idx))
    assert full_result.k_full > 0.0

    # Test beta floor binding check in calculate_full_portfolio
    # We use mock.patch to return negative value for math.sqrt to force k_full under floor
    hedge_direct = CvaHedge(
        hedge_id="h-direct",
        source_row_id="h-row-3",
        counterparty_id="cp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=10_000.0,
        remaining_maturity=2.5,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-3",
    )
    with mock.patch("math.sqrt", return_value=-10.0):
        full_result_floor = calculate_full_portfolio((cp,), (ns,), (hedge_direct,))
        assert full_result_floor.beta_floor_binding is True
