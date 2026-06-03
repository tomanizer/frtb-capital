from __future__ import annotations

import inspect
from datetime import date
from typing import NoReturn

import frtb_common.arrow_conversion as arrow_conversion_module
import numpy as np
import pyarrow as pa
import pytest
from frtb_common import AdapterDiagnostic, DiagnosticSeverity, source_content_hash
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSensitivityBatch,
    SbmSignConvention,
    SbmSourceLineage,
    build_girr_delta_batch_from_columns,
    build_girr_delta_batch_from_sensitivities,
    build_sbm_batch_from_columns,
    calculate_sbm_capital,
    calculate_sbm_capital_from_girr_delta_batch,
    input_hash_for_sbm_batch,
    input_hash_for_sensitivities,
)
from frtb_sbm.arrow_batch import (
    build_girr_delta_batch_from_arrow,
    calculate_sbm_capital_from_girr_delta_arrow,
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


def _batch_columns(sensitivities: tuple[SbmSensitivity, ...]) -> dict[str, list[object]]:
    return {
        "sensitivity_ids": [item.sensitivity_id for item in sensitivities],
        "source_row_ids": [item.source_row_id for item in sensitivities],
        "desk_ids": [item.desk_id for item in sensitivities],
        "legal_entities": [item.legal_entity for item in sensitivities],
        "risk_classes": [item.risk_class.value for item in sensitivities],
        "risk_measures": [item.risk_measure.value for item in sensitivities],
        "buckets": [item.bucket for item in sensitivities],
        "risk_factors": [item.risk_factor for item in sensitivities],
        "amounts": [item.amount for item in sensitivities],
        "amount_currencies": [item.amount_currency for item in sensitivities],
        "sign_conventions": [item.sign_convention.value for item in sensitivities],
        "tenors": [item.tenor for item in sensitivities],
        "lineage_source_systems": [item.lineage.source_system for item in sensitivities],
        "lineage_source_files": [item.lineage.source_file for item in sensitivities],
    }


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def test_row_builder_produces_immutable_numpy_batch_and_row_equivalent_hash() -> None:
    sensitivities = _sensitivities()

    batch = build_girr_delta_batch_from_sensitivities(sensitivities)

    assert isinstance(batch, SbmSensitivityBatch)
    assert batch.row_count == len(sensitivities)
    assert batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert input_hash_for_sbm_batch(batch) == input_hash_for_sensitivities(sensitivities)
    assert batch.risk_class is SbmRiskClass.GIRR
    assert batch.risk_measure is SbmRiskMeasure.DELTA
    assert isinstance(batch.amounts, np.ndarray)
    assert isinstance(batch.sensitivity_ids, np.ndarray)
    assert not batch.amounts.flags.writeable
    assert not batch.sensitivity_ids.flags.writeable
    assert not any(isinstance(value, SbmSensitivity) for value in batch.__dict__.values())


def test_generic_column_builder_accepts_girr_vega_metadata_without_row_dataclasses() -> None:
    batch = build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.GIRR,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        sensitivity_ids=["vega-001", "vega-002"],
        source_row_ids=["row-vega-001", "row-vega-002"],
        desk_ids=["rates", "rates"],
        legal_entities=["LE-001", "LE-001"],
        risk_classes=[SbmRiskClass.GIRR, SbmRiskClass.GIRR.value],
        risk_measures=[SbmRiskMeasure.VEGA.value, SbmRiskMeasure.VEGA],
        buckets=["2", "2"],
        risk_factors=["USD", "USD"],
        amounts=[100.0, -25.0],
        amount_currencies=["USD", "USD"],
        sign_conventions=[SbmSignConvention.RECEIVE, SbmSignConvention.RECEIVE.value],
        tenors=["5y", "10y"],
        option_tenors=["1y", "6m"],
        liquidity_horizon_days=[60, 60],
        lineage_source_systems=["unit-test", "unit-test"],
        lineage_source_files=["girr-vega.csv", "girr-vega.csv"],
    )

    assert batch.risk_class is SbmRiskClass.GIRR
    assert batch.risk_measure is SbmRiskMeasure.VEGA
    assert batch.row_count == 2
    assert batch.risk_classes.tolist() == [SbmRiskClass.GIRR.value, SbmRiskClass.GIRR.value]
    assert batch.risk_measures.tolist() == [SbmRiskMeasure.VEGA.value, SbmRiskMeasure.VEGA.value]
    assert batch.sign_conventions.tolist() == [
        SbmSignConvention.RECEIVE.value,
        SbmSignConvention.RECEIVE.value,
    ]
    assert batch.option_tenors is not None
    assert batch.option_tenors.tolist() == ["1y", "6m"]
    assert not any(isinstance(value, SbmSensitivity) for value in batch.__dict__.values())


def test_generic_column_builder_accepts_fx_delta_without_tenor_axis() -> None:
    batch = build_sbm_batch_from_columns(
        expected_risk_class=SbmRiskClass.FX,
        expected_risk_measure=SbmRiskMeasure.DELTA,
        sensitivity_ids=["fx-eur", "fx-gbp"],
        source_row_ids=["row-fx-001", "row-fx-002"],
        desk_ids=["fx", "fx"],
        legal_entities=["LE-001", "LE-001"],
        risk_classes=[SbmRiskClass.FX.value, SbmRiskClass.FX.value],
        risk_measures=[SbmRiskMeasure.DELTA.value, SbmRiskMeasure.DELTA.value],
        buckets=["EUR", "GBP"],
        risk_factors=["EUR", "GBP"],
        amounts=[100.0, 200.0],
        amount_currencies=["USD", "USD"],
        sign_conventions=[SbmSignConvention.RECEIVE.value, SbmSignConvention.PAY.value],
        tenors=[None, ""],
        lineage_source_systems=["unit-test", "unit-test"],
        lineage_source_files=["fx.csv", "fx.csv"],
    )

    assert batch.risk_class is SbmRiskClass.FX
    assert batch.risk_measure is SbmRiskMeasure.DELTA
    assert batch.tenors.tolist() == [None, ""]
    assert batch.row_count == 2


def test_generic_column_builder_rejects_mixed_homogeneous_path_columns() -> None:
    columns = _batch_columns(_sensitivities()[:2])

    with pytest.raises(SbmInputError, match="batch only accepts GIRR sensitivities"):
        build_sbm_batch_from_columns(
            **(columns | {"risk_classes": [SbmRiskClass.GIRR.value, SbmRiskClass.FX.value]}),
            expected_risk_class=SbmRiskClass.GIRR,
            expected_risk_measure=SbmRiskMeasure.DELTA,
        )

    with pytest.raises(SbmInputError, match="batch only accepts DELTA sensitivities"):
        mixed_measures = [SbmRiskMeasure.DELTA.value, SbmRiskMeasure.VEGA.value]
        build_sbm_batch_from_columns(
            **(columns | {"risk_measures": mixed_measures}),
            expected_risk_class=SbmRiskClass.GIRR,
            expected_risk_measure=SbmRiskMeasure.DELTA,
        )


def test_arrow_batch_batch_matches_row_batch_and_preserves_handoff_metadata() -> None:
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

    arrow_batch = build_girr_delta_batch_from_arrow(handoff)

    assert arrow_batch.input_hash == row_batch.input_hash
    assert arrow_batch.source_hash == source_hash
    assert arrow_batch.handoff_hash is not None
    assert arrow_batch.diagnostics == (diagnostic.as_dict(),)
    np.testing.assert_array_equal(arrow_batch.sensitivity_ids, row_batch.sensitivity_ids)
    np.testing.assert_array_equal(arrow_batch.buckets, row_batch.buckets)
    np.testing.assert_array_equal(arrow_batch.risk_factors, row_batch.risk_factors)
    np.testing.assert_allclose(arrow_batch.amounts, row_batch.amounts)


def test_arrow_batch_uses_zero_copy_float64_amount_column_when_possible() -> None:
    sensitivities = _sensitivities()
    handoff = normalize_girr_delta_arrow_table(_arrow_table(sensitivities))

    arrow_batch = build_girr_delta_batch_from_arrow(handoff)

    amount_view = handoff.accepted.column("amount").chunk(0).to_numpy(zero_copy_only=True)
    assert np.shares_memory(arrow_batch.amounts, amount_view)
    np.testing.assert_allclose(arrow_batch.amounts, [item.amount for item in sensitivities])


def test_sbm_handoff_wraps_arrow_object_conversion_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handoff = normalize_girr_delta_arrow_table(_arrow_table(_sensitivities()))

    def fail_arrow_object_array(_column: pa.ChunkedArray) -> NoReturn:
        raise pa.ArrowInvalid("forced conversion failure")

    monkeypatch.setattr(arrow_conversion_module, "arrow_object_array", fail_arrow_object_array)

    with pytest.raises(SbmInputError, match=r"forced conversion failure .*sensitivity_id") as exc:
        build_girr_delta_batch_from_arrow(handoff)

    assert exc.value.field == "sensitivity_id"
    assert isinstance(exc.value.__cause__, pa.ArrowInvalid)


def test_arrow_batch_handles_chunked_dictionary_text_columns() -> None:
    sensitivities = _sensitivities()
    table = pa.concat_tables(
        [
            _arrow_table(sensitivities[:2]),
            _arrow_table(sensitivities[2:]),
        ]
    )
    row_batch = build_girr_delta_batch_from_sensitivities(sensitivities)

    arrow_batch = build_girr_delta_batch_from_arrow(normalize_girr_delta_arrow_table(table))

    assert table.column("risk_class").num_chunks == 2
    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(arrow_batch.buckets, row_batch.buckets)
    np.testing.assert_array_equal(arrow_batch.risk_factors, row_batch.risk_factors)


def test_arrow_batch_rejects_non_finite_optional_float_columns() -> None:
    sensitivities = _sensitivities()[:1]
    table = _arrow_table(sensitivities).append_column(
        "up_shock_amount",
        pa.array([float("nan")], type=pa.float64()),
    )
    handoff = normalize_girr_delta_arrow_table(table)

    with pytest.raises(SbmInputError, match="value must be finite"):
        build_girr_delta_batch_from_arrow(handoff)


def test_column_builder_rejects_malformed_source_column_maps() -> None:
    columns = _batch_columns(_sensitivities()[:1])

    with pytest.raises(SbmInputError, match="source column map entries must be field pairs"):
        build_girr_delta_batch_from_columns(
            **columns,
            source_column_maps=(("bad",),),
        )


def test_column_builder_rejects_string_mapping_citation_rows() -> None:
    columns = _batch_columns(_sensitivities()[:1])

    with pytest.raises(SbmInputError, match="mapping_citation_ids rows"):
        build_girr_delta_batch_from_columns(
            **columns,
            mapping_citation_ids=("abc",),
        )


def test_row_and_arrow_calculation_paths_produce_same_girr_delta_capital() -> None:
    sensitivities = _sensitivities()
    context = _context()
    handoff = normalize_girr_delta_arrow_table(_arrow_table(sensitivities))
    arrow_batch = build_girr_delta_batch_from_arrow(handoff)

    row_result = calculate_sbm_capital(sensitivities, context=context)
    batch_result = calculate_sbm_capital_from_girr_delta_batch(arrow_batch, context=context)
    handoff_result = calculate_sbm_capital_from_girr_delta_arrow(handoff, context=context)

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
    batch = build_girr_delta_batch_from_arrow(
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


def test_arrow_batch_builder_does_not_depend_on_row_dataclass_construction() -> None:
    import frtb_sbm.arrow_batch as arrow_batch

    source = inspect.getsource(arrow_batch)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source
