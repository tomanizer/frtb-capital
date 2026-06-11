from __future__ import annotations

from datetime import date

import pyarrow as pa
import pytest
from frtb_sbm import (
    SBM_BATCH_PATH_ORDER,
    SBM_BATCH_SPECS,
    SbmBatchSpec,
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    build_sbm_batch_from_arrow,
    calculate_sbm_capital,
    calculate_sbm_capital_from_arrow,
    calculate_sbm_capital_from_batch,
    input_hash_for_batch,
    normalize_sbm_arrow_table,
)


def test_sbm_registry_covers_supported_matrix() -> None:
    expected_paths = {
        (risk_class, risk_measure) for risk_class in SbmRiskClass for risk_measure in SbmRiskMeasure
    }

    assert set(SBM_BATCH_SPECS) == expected_paths
    assert set(SBM_BATCH_PATH_ORDER) == expected_paths
    assert len(SBM_BATCH_PATH_ORDER) == len(expected_paths)
    for path, spec in SBM_BATCH_SPECS.items():
        assert isinstance(spec, SbmBatchSpec)
        assert spec.path == path
        assert spec.path_key == f"{path[0].value.lower()}_{path[1].value.lower()}"
        assert spec.label


def test_generic_batch_capital_path_matches_row_api() -> None:
    context = sample_context()
    sensitivity = sample_fx_delta_sensitivity()

    batch = build_sbm_batch(
        (sensitivity,),
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
        context=context,
    )
    batch_result = calculate_sbm_capital_from_batch(batch, context=context)
    row_result = calculate_sbm_capital((sensitivity,), context=context)

    assert input_hash_for_batch(batch) == row_result.input_hash
    assert batch_result.input_hash == row_result.input_hash
    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert batch_result.risk_classes[0].risk_class is SbmRiskClass.FX
    assert batch_result.risk_classes[0].risk_measure is SbmRiskMeasure.DELTA


def test_generic_arrow_path_matches_batch_api() -> None:
    context = sample_context()
    handoff = normalize_sbm_arrow_table(
        fx_delta_arrow_table(),
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
    )

    batch = build_sbm_batch_from_arrow(
        handoff,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
        context=context,
    )
    arrow_result = calculate_sbm_capital_from_arrow(
        handoff,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
        context=context,
    )
    batch_result = calculate_sbm_capital_from_batch(batch, context=context)

    assert batch.accepted_row_dataclasses_materialized == 0
    assert arrow_result.input_hash == batch_result.input_hash
    assert arrow_result.total_capital == pytest.approx(batch_result.total_capital)


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-registry-test",
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def sample_fx_delta_sensitivity() -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id="fx-eur",
        source_row_id="row-fx",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="EUR",
        risk_factor="EUR",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=SbmSourceLineage(
            source_system="synthetic-risk",
            source_file="sbm.csv",
            source_row_id="row-fx",
            source_column_map=(("DeltaUSD", "amount"),),
        ),
    )


def fx_delta_arrow_table() -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": ["fx-eur"],
            "source_row_id": ["row-fx"],
            "desk_id": ["rates-desk"],
            "legal_entity": ["LE-001"],
            "risk_class": [SbmRiskClass.FX.value],
            "risk_measure": [SbmRiskMeasure.DELTA.value],
            "bucket": ["EUR"],
            "risk_factor": ["EUR"],
            "amount": [1_000_000.0],
            "amount_currency": ["USD"],
            "sign_convention": [SbmSignConvention.RECEIVE.value],
            "lineage_source_system": ["synthetic-risk"],
            "lineage_source_file": ["sbm.csv"],
        }
    )
