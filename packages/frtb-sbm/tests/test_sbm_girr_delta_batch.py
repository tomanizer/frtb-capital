from __future__ import annotations

import inspect
from datetime import date

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import AdapterDiagnostic, DiagnosticSeverity, source_content_hash
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSensitivityBatch,
    SbmSignConvention,
    SbmSourceLineage,
    build_girr_delta_batch_from_sensitivities,
    calculate_sbm_capital,
    calculate_sbm_capital_from_girr_delta_batch,
    input_hash_for_sensitivities,
)
from frtb_sbm.arrow_handoff import (
    build_girr_delta_batch_from_handoff,
    calculate_sbm_capital_from_girr_delta_handoff,
    normalize_girr_delta_arrow_table,
)
from frtb_sbm.factor_grid import (
    net_girr_delta_sensitivity_batch,
    net_girr_delta_weighted_sensitivities,
)
from frtb_sbm.weighted_sensitivity import weight_girr_delta_sensitivities


def _context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="run-girr-delta-batch",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def _sensitivity(
    index: int,
    *,
    amount: float,
    risk_factor: str,
    tenor: str,
    bucket: str = "2",
) -> SbmSensitivity:
    row_id = f"row-{index:04d}"
    return SbmSensitivity(
        sensitivity_id=f"sens-{index:04d}",
        source_row_id=row_id,
        desk_id="rates",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        tenor=tenor,
        lineage=SbmSourceLineage(
            source_system="unit-test",
            source_file="girr-delta-batch.csv",
            source_row_id=row_id,
        ),
    )


def _sensitivities() -> tuple[SbmSensitivity, ...]:
    return (
        _sensitivity(1, amount=100.0, risk_factor="USD-OIS", tenor="5y"),
        _sensitivity(2, amount=200.0, risk_factor="USD-OIS", tenor="5y"),
        _sensitivity(3, amount=-25.0, risk_factor="USD-OIS", tenor="5y"),
        _sensitivity(4, amount=50.0, risk_factor="USD-LIBOR", tenor="5y"),
        _sensitivity(5, amount=10.0, risk_factor="EUR-OIS", tenor="1y", bucket="1"),
    )


def _arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
    return pa.table(
        {
            "sensitivity_id": [item.sensitivity_id for item in sensitivities],
            "source_row_id": [item.source_row_id for item in sensitivities],
            "desk_id": [item.desk_id for item in sensitivities],
            "legal_entity": [item.legal_entity for item in sensitivities],
            "risk_class": _dictionary([item.risk_class.value for item in sensitivities]),
            "risk_measure": _dictionary([item.risk_measure.value for item in sensitivities]),
            "bucket": _dictionary([item.bucket for item in sensitivities]),
            "risk_factor": _dictionary([item.risk_factor for item in sensitivities]),
            "amount": pa.array([item.amount for item in sensitivities], type=pa.float64()),
            "amount_currency": _dictionary([item.amount_currency for item in sensitivities]),
            "sign_convention": _dictionary([item.sign_convention.value for item in sensitivities]),
            "tenor": _dictionary([item.tenor for item in sensitivities]),
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def test_row_builder_produces_immutable_numpy_batch_and_row_equivalent_hash() -> None:
    sensitivities = _sensitivities()

    batch = build_girr_delta_batch_from_sensitivities(sensitivities)

    assert isinstance(batch, SbmSensitivityBatch)
    assert batch.row_count == len(sensitivities)
    assert batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert isinstance(batch.amounts, np.ndarray)
    assert isinstance(batch.sensitivity_ids, np.ndarray)
    assert not batch.amounts.flags.writeable
    assert not batch.sensitivity_ids.flags.writeable
    assert not any(isinstance(value, SbmSensitivity) for value in batch.__dict__.values())


def test_arrow_handoff_batch_matches_row_batch_and_preserves_handoff_metadata() -> None:
    sensitivities = _sensitivities()
    row_batch = build_girr_delta_batch_from_sensitivities(sensitivities)
    source_hash = source_content_hash("synthetic GIRR delta source")
    diagnostic = AdapterDiagnostic(
        code="sbm.girr_delta.synthetic",
        message="synthetic test handoff",
        severity=DiagnosticSeverity.INFO,
    )
    handoff = normalize_girr_delta_arrow_table(
        _arrow_table(sensitivities),
        source_hash=source_hash,
        diagnostics=(diagnostic,),
    )

    arrow_batch = build_girr_delta_batch_from_handoff(handoff)

    assert arrow_batch.input_hash == row_batch.input_hash
    assert arrow_batch.source_hash == source_hash
    assert arrow_batch.handoff_hash is not None
    assert arrow_batch.diagnostics == (diagnostic.as_dict(),)
    np.testing.assert_array_equal(arrow_batch.sensitivity_ids, row_batch.sensitivity_ids)
    np.testing.assert_array_equal(arrow_batch.buckets, row_batch.buckets)
    np.testing.assert_array_equal(arrow_batch.risk_factors, row_batch.risk_factors)
    np.testing.assert_allclose(arrow_batch.amounts, row_batch.amounts)


def test_row_and_arrow_calculation_paths_produce_same_girr_delta_capital() -> None:
    sensitivities = _sensitivities()
    context = _context()
    handoff = normalize_girr_delta_arrow_table(_arrow_table(sensitivities))
    arrow_batch = build_girr_delta_batch_from_handoff(handoff)

    row_result = calculate_sbm_capital(sensitivities, context=context)
    batch_result = calculate_sbm_capital_from_girr_delta_batch(arrow_batch, context=context)
    handoff_result = calculate_sbm_capital_from_girr_delta_handoff(handoff, context=context)

    assert batch_result.total_capital == pytest.approx(row_result.total_capital)
    assert handoff_result.total_capital == pytest.approx(row_result.total_capital)
    assert batch_result.input_hash == row_result.input_hash
    assert handoff_result.input_hash == row_result.input_hash
    assert (
        batch_result.risk_classes[0].selected_scenario
        is row_result.risk_classes[0].selected_scenario
    )


def test_batch_factor_grid_converges_with_existing_row_factor_grid() -> None:
    sensitivities = _sensitivities()
    batch = build_girr_delta_batch_from_handoff(
        normalize_girr_delta_arrow_table(_arrow_table(sensitivities))
    )
    row_weighted = weight_girr_delta_sensitivities(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )
    row_grid = net_girr_delta_weighted_sensitivities(sensitivities, row_weighted)

    batch_grid = net_girr_delta_sensitivity_batch(
        batch,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert batch_grid.raw_row_count == len(sensitivities)
    assert batch_grid.factor_count == row_grid.factor_count
    assert batch_grid.factor_count < batch_grid.raw_row_count
    assert batch_grid.tenor_by_id == row_grid.tenor_by_id
    assert batch_grid.risk_factor_by_id == row_grid.risk_factor_by_id
    assert [
        (
            item.sensitivity_id,
            item.raw_amount,
            item.risk_weight,
            item.scaled_amount,
            item.factor_key,
            item.contributing_sensitivity_ids,
        )
        for item in batch_grid.weighted_sensitivities
    ] == [
        (
            item.sensitivity_id,
            item.raw_amount,
            item.risk_weight,
            item.scaled_amount,
            item.factor_key,
            item.contributing_sensitivity_ids,
        )
        for item in row_grid.weighted_sensitivities
    ]


def test_arrow_handoff_builder_does_not_depend_on_row_dataclass_construction() -> None:
    import frtb_sbm.arrow_handoff as arrow_handoff

    source = inspect.getsource(arrow_handoff)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source
