from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import TabularHandoffError, UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    CURVATURE_CAPITAL_REQUIREMENT_ID,
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_girr_curvature_batch_from_sensitivities,
    calculate_girr_curvature_risk_class_capital,
    calculate_sbm_capital,
    curvature_capital_unsupported_feature,
    curvature_worst_branch,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_risk_class_measure_supported,
    input_hash_for_sensitivities,
    parse_curvature_input,
    select_girr_curvature_branches_from_batch,
    validate_curvature_sensitivities,
    validate_girr_curvature_batch,
    weight_girr_curvature_sensitivities,
)
from frtb_sbm.arrow_handoff import (
    build_girr_curvature_batch_from_handoff,
    normalize_girr_curvature_arrow_table,
)


def sample_lineage() -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id="row-curv-001",
    )


def sample_curvature_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "curv-001",
        "source_row_id": "row-curv-001",
        "desk_id": "rates-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.GIRR,
        "risk_measure": SbmRiskMeasure.CURVATURE,
        "bucket": "1",
        "risk_factor": "USD",
        "amount": 0.0,
        "amount_currency": "USD",
        "tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_lineage(),
        "up_shock_amount": -12_000.0,
        "down_shock_amount": -18_000.0,
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def sample_context(**overrides: object) -> SbmCalculationContext:
    fields = {
        "run_id": "run-curv-001",
        "calculation_date": date(2026, 5, 30),
        "base_currency": "USD",
        "reporting_currency": "USD",
        "profile_id": SbmRegulatoryProfile.BASEL_MAR21.value,
    }
    fields.update(overrides)
    return SbmCalculationContext(**fields)  # type: ignore[arg-type]


def sample_curvature_arrow_table(sensitivities: tuple[SbmSensitivity, ...]) -> pa.Table:
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
            "up_shock_amount": pa.array(
                [item.up_shock_amount for item in sensitivities],
                type=pa.float64(),
            ),
            "down_shock_amount": pa.array(
                [item.down_shock_amount for item in sensitivities],
                type=pa.float64(),
            ),
            "lineage_source_system": [item.lineage.source_system for item in sensitivities],
            "lineage_source_file": [item.lineage.source_file for item in sensitivities],
        }
    )


def _dictionary(values: list[str | None]) -> pa.Array:
    return pa.array(values).dictionary_encode()


def _replace_column(table: pa.Table, name: str, values: pa.Array) -> pa.Table:
    column_index = table.schema.get_field_index(name)
    assert column_index >= 0
    return table.set_column(column_index, name, values)


def test_parse_curvature_input_builds_canonical_record() -> None:
    sensitivity = sample_curvature_sensitivity()
    parsed = parse_curvature_input(
        sensitivity,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert parsed.sensitivity_id == "curv-001"
    assert parsed.risk_class is SbmRiskClass.GIRR
    assert parsed.bucket == "1"
    assert parsed.risk_factor == "USD"
    assert parsed.amount_currency == "USD"
    assert parsed.up_shock_amount == -12_000.0
    assert parsed.down_shock_amount == -18_000.0
    assert parsed.citation_ids == ("basel_mar21_curvature",)


def test_validate_curvature_sensitivities_orders_deterministically() -> None:
    second = sample_curvature_sensitivity(
        sensitivity_id="curv-002",
        source_row_id="row-curv-002",
        bucket="2",
        lineage=replace(sample_lineage(), source_row_id="row-curv-002"),
    )
    first = sample_curvature_sensitivity()

    validated = validate_curvature_sensitivities(
        (second, first),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert [item.sensitivity_id for item in validated] == ["curv-001", "curv-002"]


def test_validate_curvature_sensitivities_rejects_missing_shock_amounts() -> None:
    with pytest.raises(SbmInputError, match="curvature inputs require") as exc_info:
        validate_curvature_sensitivities(
            (sample_curvature_sensitivity(up_shock_amount=None),),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
    assert exc_info.value.field == "up_shock_amount"


def test_validate_curvature_sensitivities_rejects_non_curvature_rows() -> None:
    delta = sample_curvature_sensitivity(
        sensitivity_id="delta-001",
        risk_measure=SbmRiskMeasure.DELTA,
        amount=1_000_000.0,
        up_shock_amount=None,
        down_shock_amount=None,
    )
    with pytest.raises(SbmInputError, match="only CURVATURE rows") as exc_info:
        validate_curvature_sensitivities(
            (delta,),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
    assert exc_info.value.field == "risk_measure"


def test_curvature_worst_branch_selects_more_negative_shock() -> None:
    assert curvature_worst_branch(-12_000.0, -18_000.0) == "down"
    assert curvature_worst_branch(-18_000.0, -12_000.0) == "up"
    assert curvature_worst_branch(-10_000.0, -10_000.0) == "up"


def test_girr_curvature_batch_and_handoff_preserve_separate_shock_arrays() -> None:
    sensitivities = (
        sample_curvature_sensitivity(),
        sample_curvature_sensitivity(
            sensitivity_id="curv-002",
            source_row_id="row-curv-002",
            risk_factor="EUR",
            tenor="10y",
            up_shock_amount=-22_000.0,
            down_shock_amount=-13_000.0,
            lineage=replace(sample_lineage(), source_row_id="row-curv-002"),
        ),
    )
    row_batch = build_girr_curvature_batch_from_sensitivities(sensitivities)
    handoff = normalize_girr_curvature_arrow_table(sample_curvature_arrow_table(sensitivities))

    arrow_batch = build_girr_curvature_batch_from_handoff(handoff)

    assert arrow_batch.input_hash == row_batch.input_hash
    assert arrow_batch.input_hash == input_hash_for_sensitivities(sensitivities)
    assert arrow_batch.risk_class is SbmRiskClass.GIRR
    assert arrow_batch.risk_measure is SbmRiskMeasure.CURVATURE
    assert arrow_batch.up_shock_amounts is not None
    assert arrow_batch.down_shock_amounts is not None
    np.testing.assert_allclose(
        np.asarray(arrow_batch.up_shock_amounts, dtype=np.float64),
        [-12_000.0, -22_000.0],
    )
    np.testing.assert_allclose(
        np.asarray(arrow_batch.down_shock_amounts, dtype=np.float64),
        [-18_000.0, -13_000.0],
    )
    assert not any(isinstance(value, SbmSensitivity) for value in arrow_batch.__dict__.values())


def test_girr_curvature_branch_selection_from_batch_matches_row_helper() -> None:
    sensitivities = (
        sample_curvature_sensitivity(
            sensitivity_id="curv-002",
            source_row_id="row-curv-002",
            risk_factor="USD",
            up_shock_amount=-22_000.0,
            down_shock_amount=-13_000.0,
            lineage=replace(sample_lineage(), source_row_id="row-curv-002"),
        ),
        sample_curvature_sensitivity(),
    )
    batch = build_girr_curvature_batch_from_handoff(
        normalize_girr_curvature_arrow_table(sample_curvature_arrow_table(sensitivities))
    )

    records = select_girr_curvature_branches_from_batch(
        batch,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert [record.sensitivity_id for record in records] == ["curv-001", "curv-002"]
    assert [record.selected_branch for record in records] == [
        curvature_worst_branch(-12_000.0, -18_000.0),
        curvature_worst_branch(-22_000.0, -13_000.0),
    ]
    assert [record.up_shock_amount for record in records] == [-12_000.0, -22_000.0]
    assert [record.down_shock_amount for record in records] == [-18_000.0, -13_000.0]
    assert all(record.citation_ids == ("basel_mar21_curvature",) for record in records)


def test_girr_curvature_handoff_rejects_missing_shock_column() -> None:
    table = sample_curvature_arrow_table((sample_curvature_sensitivity(),)).drop_columns(
        ["up_shock_amount"]
    )

    with pytest.raises(TabularHandoffError, match="Required column 'up_shock_amount'"):
        normalize_girr_curvature_arrow_table(table)


def test_girr_curvature_handoff_rejects_null_shock_column() -> None:
    table = _replace_column(
        sample_curvature_arrow_table((sample_curvature_sensitivity(),)),
        "down_shock_amount",
        pa.array([None], type=pa.float64()),
    )

    with pytest.raises(TabularHandoffError, match="Column 'down_shock_amount' contains nulls"):
        normalize_girr_curvature_arrow_table(table)


@pytest.mark.parametrize(
    ("column_name", "values", "expected"),
    [
        ("up_shock_amount", pa.array(["not-a-number"], type=pa.string()), "value must be numeric"),
        ("down_shock_amount", pa.array([float("inf")], type=pa.float64()), "value must be finite"),
    ],
)
def test_girr_curvature_batch_build_rejects_bad_shock_values(
    column_name: str,
    values: pa.Array,
    expected: str,
) -> None:
    table = _replace_column(
        sample_curvature_arrow_table((sample_curvature_sensitivity(),)),
        column_name,
        values,
    )
    handoff = normalize_girr_curvature_arrow_table(table)

    with pytest.raises(SbmInputError, match=expected):
        build_girr_curvature_batch_from_handoff(handoff)


def test_validate_girr_curvature_batch_does_not_enable_capital_support() -> None:
    batch = build_girr_curvature_batch_from_handoff(
        normalize_girr_curvature_arrow_table(
            sample_curvature_arrow_table((sample_curvature_sensitivity(),))
        )
    )

    assert (
        validate_girr_curvature_batch(
            batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
        is batch
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            SbmRiskClass.GIRR,
            SbmRiskMeasure.CURVATURE,
        )


def test_girr_curvature_arrow_handoff_path_does_not_materialize_sensitivity_rows() -> None:
    import frtb_sbm.arrow_handoff as arrow_handoff

    source = inspect.getsource(arrow_handoff)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source


def test_weight_girr_curvature_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        weight_girr_curvature_sensitivities(
            (sample_curvature_sensitivity(),),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            reporting_currency="USD",
        )


def test_calculate_girr_curvature_risk_class_capital_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        calculate_girr_curvature_risk_class_capital(
            (sample_curvature_sensitivity(),),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            reporting_currency="USD",
        )


def test_calculate_sbm_capital_rejects_girr_curvature() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        calculate_sbm_capital(
            (sample_curvature_sensitivity(),),
            context=sample_context(),
        )


def test_curvature_capital_unsupported_feature_is_structured() -> None:
    feature = curvature_capital_unsupported_feature(SbmRegulatoryProfile.BASEL_MAR21.value)

    assert feature.feature_key == "sbm_curvature_capital"
    assert feature.dimension == "risk_measure"
    assert feature.requirement_id == CURVATURE_CAPITAL_REQUIREMENT_ID


@pytest.mark.parametrize(
    "risk_class",
    [item for item in SbmRiskClass if item is not SbmRiskClass.GIRR],
)
def test_non_girr_curvature_capital_paths_fail_closed(risk_class: SbmRiskClass) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            risk_class,
            SbmRiskMeasure.CURVATURE,
        )


def test_girr_curvature_path_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            SbmRiskClass.GIRR,
            SbmRiskMeasure.CURVATURE,
        )


def test_ensure_sbm_capital_paths_supported_rejects_girr_curvature() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        ensure_sbm_capital_paths_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            (sample_curvature_sensitivity(),),
        )
