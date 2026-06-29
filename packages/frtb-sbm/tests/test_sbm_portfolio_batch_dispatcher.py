from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date

import pyarrow as pa
import pytest
from frtb_common import NormalizedArrowTable, UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    calculate_sbm_capital,
    calculate_sbm_portfolio_capital_from_batches,
    input_hash_for_sensitivities,
)
from frtb_sbm.arrow_batch import (
    calculate_sbm_portfolio_capital_from_arrow_tables,
)
from sbm_registry_helpers import (
    build_sbm_path_from_arrow,
    normalize_commodity_curvature_arrow_table,
    normalize_commodity_delta_arrow_table,
    normalize_commodity_vega_arrow_table,
    normalize_csr_nonsec_curvature_arrow_table,
    normalize_csr_nonsec_delta_arrow_table,
    normalize_csr_nonsec_vega_arrow_table,
    normalize_csr_sec_ctp_curvature_arrow_table,
    normalize_csr_sec_ctp_delta_arrow_table,
    normalize_csr_sec_ctp_vega_arrow_table,
    normalize_csr_sec_nonctp_curvature_arrow_table,
    normalize_csr_sec_nonctp_delta_arrow_table,
    normalize_csr_sec_nonctp_vega_arrow_table,
    normalize_equity_curvature_arrow_table,
    normalize_equity_delta_arrow_table,
    normalize_equity_vega_arrow_table,
    normalize_fx_curvature_arrow_table,
    normalize_fx_delta_arrow_table,
    normalize_fx_vega_arrow_table,
    normalize_girr_curvature_arrow_table,
    normalize_girr_delta_arrow_table,
    normalize_girr_vega_arrow_table,
    normalize_sbm_path,
)

NormalizeFn = Callable[..., NormalizedArrowTable]
Path = tuple[SbmRiskClass, SbmRiskMeasure]

SUPPORTED_PATHS: tuple[Path, ...] = (
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA),
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA),
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE),
)

NORMALIZERS: dict[Path, NormalizeFn] = {
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA): normalize_girr_delta_arrow_table,
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA): normalize_girr_vega_arrow_table,
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE): normalize_girr_curvature_arrow_table,
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA): normalize_fx_delta_arrow_table,
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA): normalize_fx_vega_arrow_table,
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE): normalize_fx_curvature_arrow_table,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA): normalize_equity_delta_arrow_table,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA): normalize_equity_vega_arrow_table,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE): normalize_equity_curvature_arrow_table,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA): normalize_commodity_delta_arrow_table,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA): normalize_commodity_vega_arrow_table,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE): (normalize_commodity_curvature_arrow_table),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA): normalize_csr_nonsec_delta_arrow_table,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA): normalize_csr_nonsec_vega_arrow_table,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE): (
        normalize_csr_nonsec_curvature_arrow_table
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA): (
        normalize_csr_sec_nonctp_delta_arrow_table
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA): (normalize_csr_sec_nonctp_vega_arrow_table),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE): (
        normalize_csr_sec_nonctp_curvature_arrow_table
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA): normalize_csr_sec_ctp_delta_arrow_table,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA): normalize_csr_sec_ctp_vega_arrow_table,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE): (
        normalize_csr_sec_ctp_curvature_arrow_table
    ),
}


def test_portfolio_handoff_dispatcher_matches_row_api_for_supported_paths() -> None:
    context = sample_context()
    sensitivities = tuple(
        sample_sensitivity(index, risk_class=risk_class, risk_measure=risk_measure)
        for index, (risk_class, risk_measure) in enumerate(SUPPORTED_PATHS, start=1)
    )
    handoffs = tuple(
        NORMALIZERS[(item.risk_class, item.risk_measure)](arrow_table((item,)))
        for item in sensitivities
    )

    row_result = calculate_sbm_capital(sensitivities, context=context)
    calculation = calculate_sbm_portfolio_capital_from_arrow_tables(handoffs, context=context)

    assert calculation.accepted_row_dataclasses_materialized == 0
    assert {item.batch_count for item in calculation.path_diagnostics} == {1}
    assert {item.input_count for item in calculation.path_diagnostics} == {1}
    materialized_counts = {
        item.accepted_row_dataclasses_materialized for item in calculation.path_diagnostics
    }
    assert materialized_counts == {0}
    assert {(item.risk_class, item.risk_measure) for item in calculation.path_diagnostics} == set(
        SUPPORTED_PATHS
    )
    assert calculation.result.input_hash == input_hash_for_sensitivities(sensitivities)
    assert calculation.result.input_hash == row_result.input_hash
    assert calculation.result.total_capital == pytest.approx(row_result.total_capital)
    assert calculation.result.reconciliation is not None
    assert calculation.result.reconciliation.input_count == len(sensitivities)


def test_batch_dispatcher_concatenates_split_same_path_batches_before_capital() -> None:
    context = sample_context()
    sensitivities = (
        sample_sensitivity(1, risk_class=SbmRiskClass.FX, risk_measure=SbmRiskMeasure.DELTA),
        sample_sensitivity(2, risk_class=SbmRiskClass.FX, risk_measure=SbmRiskMeasure.DELTA),
    )
    handoff_1 = normalize_sbm_path(
        SbmRiskClass.FX, SbmRiskMeasure.DELTA, arrow_table((sensitivities[0],))
    )
    handoff_2 = normalize_sbm_path(
        SbmRiskClass.FX, SbmRiskMeasure.DELTA, arrow_table((sensitivities[1],))
    )
    batch_1 = build_sbm_path_from_arrow(SbmRiskClass.FX, SbmRiskMeasure.DELTA, handoff_1)
    batch_2 = build_sbm_path_from_arrow(SbmRiskClass.FX, SbmRiskMeasure.DELTA, handoff_2)

    row_result = calculate_sbm_capital(sensitivities, context=context)
    calculation = calculate_sbm_portfolio_capital_from_batches((batch_1, batch_2), context=context)

    assert calculation.accepted_row_dataclasses_materialized == 0
    assert len(calculation.path_diagnostics) == 1
    assert calculation.path_diagnostics[0].batch_count == 2
    assert calculation.path_diagnostics[0].input_count == 2
    assert len(calculation.result.risk_classes) == 1
    assert calculation.result.input_hash == row_result.input_hash
    assert calculation.result.total_capital == pytest.approx(row_result.total_capital)


def test_row_compatibility_batches_report_materialized_input_dataclasses() -> None:
    context = sample_context()
    sensitivities = (
        sample_sensitivity(1, risk_class=SbmRiskClass.FX, risk_measure=SbmRiskMeasure.DELTA),
        sample_sensitivity(2, risk_class=SbmRiskClass.FX, risk_measure=SbmRiskMeasure.DELTA),
    )
    batch = build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.DELTA)

    calculation = calculate_sbm_portfolio_capital_from_batches((batch,), context=context)

    assert calculation.accepted_row_dataclasses_materialized == 2
    assert calculation.path_diagnostics[0].accepted_row_dataclasses_materialized == 2


def test_arrow_table_dispatcher_rejects_mixed_path_table() -> None:
    context = sample_context()
    fx_row = replace(
        sample_sensitivity(2, risk_class=SbmRiskClass.FX, risk_measure=SbmRiskMeasure.DELTA),
        tenor="5y",
    )
    mixed_rows = (
        sample_sensitivity(1, risk_class=SbmRiskClass.GIRR, risk_measure=SbmRiskMeasure.DELTA),
        fx_row,
    )
    normalized_table = normalize_sbm_path(
        SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, arrow_table(mixed_rows)
    )

    with pytest.raises(
        SbmInputError,
        match="arrow table 1 must be homogeneous by risk_class and risk_measure",
    ):
        calculate_sbm_portfolio_capital_from_arrow_tables((normalized_table,), context=context)


def test_batch_dispatcher_reports_batch_field_for_invalid_batch_inputs() -> None:
    context = sample_context()

    with pytest.raises(SbmInputError) as non_iterable_exc:
        calculate_sbm_portfolio_capital_from_batches(object(), context=context)
    assert non_iterable_exc.value.field == "batches"

    with pytest.raises(SbmInputError) as wrong_member_exc:
        calculate_sbm_portfolio_capital_from_batches((object(),), context=context)
    assert wrong_member_exc.value.field == "batches"


def test_batch_dispatcher_supports_pra_uk_crr_profile() -> None:
    handoff = normalize_sbm_path(
        SbmRiskClass.GIRR,
        SbmRiskMeasure.DELTA,
        arrow_table(
            (
                sample_sensitivity(
                    1,
                    risk_class=SbmRiskClass.GIRR,
                    risk_measure=SbmRiskMeasure.DELTA,
                ),
            )
        ),
    )
    context = SbmCalculationContext(
        run_id="sbm-portfolio-dispatch-pra-uk-crr",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.PRA_UK_CRR.value,
    )

    calculation = calculate_sbm_portfolio_capital_from_arrow_tables((handoff,), context=context)
    assert calculation.result.total_capital > 0.0


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-portfolio-dispatch",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_sensitivity(
    index: int,
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> SbmSensitivity:
    bucket, risk_factor, qualifier, tenor = path_metadata(risk_class, risk_measure, index)
    return SbmSensitivity(
        sensitivity_id=f"{risk_class.value.lower()}-{risk_measure.value.lower()}-{index:03d}",
        source_row_id=f"row-{index:03d}",
        desk_id="portfolio-desk",
        legal_entity="LE-001",
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=0.0 if risk_measure is SbmRiskMeasure.CURVATURE else 1_000.0 + index,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=SbmSourceLineage(
            source_system="unit-test",
            source_file="sbm-portfolio.csv",
            source_row_id=f"row-{index:03d}",
        ),
        qualifier=qualifier,
        tenor=tenor,
        option_tenor="1y" if risk_measure is SbmRiskMeasure.VEGA else None,
        up_shock_amount=200.0 + index if risk_measure is SbmRiskMeasure.CURVATURE else None,
        down_shock_amount=80.0 + index if risk_measure is SbmRiskMeasure.CURVATURE else None,
    )


def path_metadata(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    index: int,
) -> tuple[str, str, str | None, str | None]:
    if risk_class is SbmRiskClass.GIRR:
        risk_factor = "USD-OIS" if risk_measure is SbmRiskMeasure.DELTA else "USD"
        return "2", risk_factor, None, "5y"
    if risk_class is SbmRiskClass.FX:
        currency = "EUR" if index % 2 else "GBP"
        return currency, currency, None, None
    if risk_class is SbmRiskClass.EQUITY:
        return "5", "SPOT", f"ISS-{index}", None
    if risk_class is SbmRiskClass.COMMODITY:
        tenor = "3m" if risk_measure is SbmRiskMeasure.DELTA else None
        return "2", "WTI", f"LOC-{index}", tenor
    if risk_class is SbmRiskClass.CSR_NONSEC:
        tenor = "5y" if risk_measure is SbmRiskMeasure.DELTA else None
        return "4", "BOND", f"ISS-{index}", tenor
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        tenor = "5y" if risk_measure is SbmRiskMeasure.DELTA else None
        return "1", "BOND", f"TR-{index}", tenor
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        tenor = "5y" if risk_measure is SbmRiskMeasure.DELTA else None
        return "3", "BOND", f"UND-{index}", tenor
    raise AssertionError(f"unexpected risk class {risk_class}")


def arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    columns: dict[str, object] = {
        "sensitivity_id": [item.sensitivity_id for item in sensitivities],
        "source_row_id": [item.source_row_id for item in sensitivities],
        "desk_id": [item.desk_id for item in sensitivities],
        "legal_entity": [item.legal_entity for item in sensitivities],
        "risk_class": dictionary([item.risk_class.value for item in sensitivities]),
        "risk_measure": dictionary([item.risk_measure.value for item in sensitivities]),
        "bucket": dictionary([item.bucket for item in sensitivities]),
        "risk_factor": dictionary([item.risk_factor for item in sensitivities]),
        "amount": pa.array([item.amount for item in sensitivities], type=pa.float64()),
        "amount_currency": dictionary([item.amount_currency for item in sensitivities]),
        "sign_convention": dictionary([item.sign_convention.value for item in sensitivities]),
        "lineage_source_system": [item.lineage.source_system for item in sensitivities],
        "lineage_source_file": [item.lineage.source_file for item in sensitivities],
    }
    optional_columns = {
        "qualifier": [item.qualifier for item in sensitivities],
        "tenor": [item.tenor for item in sensitivities],
        "option_tenor": [item.option_tenor for item in sensitivities],
        "up_shock_amount": [item.up_shock_amount for item in sensitivities],
        "down_shock_amount": [item.down_shock_amount for item in sensitivities],
    }
    for column_name, values in optional_columns.items():
        if not any(value is not None for value in values):
            continue
        if column_name in {"up_shock_amount", "down_shock_amount"}:
            columns[column_name] = pa.array(values, type=pa.float64())
        else:
            columns[column_name] = dictionary(values)
    return pa.table(columns)


def dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()
