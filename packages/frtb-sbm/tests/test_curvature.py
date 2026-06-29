from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import NormalizedTableError, UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    CURVATURE_CAPITAL_REQUIREMENT_ID,
    FX_CURVATURE_SCALAR_1_5_FLAG,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    build_sbm_batch,
    calculate_curvature_risk_class_capital,
    calculate_girr_curvature_risk_class_capital,
    calculate_sbm_capital,
    curvature_capital_unsupported_feature,
    curvature_risk_weight,
    curvature_worst_branch,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_risk_class_measure_supported,
    parse_curvature_input,
    select_girr_curvature_branches_from_batch,
    serialize_sbm_result,
    validate_curvature_sensitivities,
    validate_girr_curvature_batch,
    weight_girr_curvature_sensitivities,
)
from sbm_registry_helpers import (
    build_sbm_path_from_arrow,
    normalize_sbm_path,
)

CURVATURE_CITATIONS = (
    "basel_mar21_curvature",
    "basel_mar21_96",
    "basel_mar21_97",
    "basel_mar21_98",
    "basel_mar21_99",
    "basel_mar21_100",
    "basel_mar21_101",
)


def build_girr_curvature_batch_from_sensitivities(sensitivities: object):
    return build_sbm_batch(sensitivities, SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE)


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
    assert parsed.citation_ids == CURVATURE_CITATIONS


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
    handoff = normalize_sbm_path(
        SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, sample_curvature_arrow_table(sensitivities)
    )

    arrow_batch = build_sbm_path_from_arrow(SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, handoff)

    assert len(arrow_batch.input_hash) == 64
    int(arrow_batch.input_hash, 16)
    assert arrow_batch.input_hash_algorithm == "arrow-columnar-v2"
    assert arrow_batch.input_hash != row_batch.input_hash
    assert len(arrow_batch.input_hash) == 64
    int(arrow_batch.input_hash, 16)
    assert arrow_batch.input_hash_algorithm == "arrow-columnar-v2"
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
    batch = build_sbm_path_from_arrow(
        SbmRiskClass.GIRR,
        SbmRiskMeasure.CURVATURE,
        normalize_sbm_path(
            SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, sample_curvature_arrow_table(sensitivities)
        ),
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
    assert all(record.citation_ids == CURVATURE_CITATIONS for record in records)


def test_girr_curvature_handoff_rejects_missing_shock_column() -> None:
    table = sample_curvature_arrow_table((sample_curvature_sensitivity(),)).drop_columns(
        ["up_shock_amount"]
    )

    with pytest.raises(NormalizedTableError, match="Required column 'up_shock_amount'"):
        normalize_sbm_path(SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, table)


def test_girr_curvature_handoff_rejects_null_shock_column() -> None:
    table = _replace_column(
        sample_curvature_arrow_table((sample_curvature_sensitivity(),)),
        "down_shock_amount",
        pa.array([None], type=pa.float64()),
    )

    with pytest.raises(NormalizedTableError, match="Column 'down_shock_amount' contains nulls"):
        normalize_sbm_path(SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, table)


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
    handoff = normalize_sbm_path(SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, table)

    with pytest.raises(SbmInputError, match=expected):
        build_sbm_path_from_arrow(SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE, handoff)


def test_validate_girr_curvature_batch_and_support_gate_accept_curvature() -> None:
    batch = build_sbm_path_from_arrow(
        SbmRiskClass.GIRR,
        SbmRiskMeasure.CURVATURE,
        normalize_sbm_path(
            SbmRiskClass.GIRR,
            SbmRiskMeasure.CURVATURE,
            sample_curvature_arrow_table((sample_curvature_sensitivity(),)),
        ),
    )

    assert (
        validate_girr_curvature_batch(
            batch,
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        )
        is batch
    )
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.CURVATURE,
    )


def test_girr_curvature_arrow_batch_path_does_not_materialize_sensitivity_rows() -> None:
    import frtb_sbm.arrow_batch as arrow_batch

    source = inspect.getsource(arrow_batch)

    assert "SbmSensitivity(" not in source
    assert "from frtb_sbm.data_models import SbmSensitivity" not in source


def test_weight_girr_curvature_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="cannot be represented"):
        weight_girr_curvature_sensitivities(
            (sample_curvature_sensitivity(),),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            reporting_currency="USD",
        )


def test_girr_curvature_engine_selects_bucket_branch_by_correlation_scenario() -> None:
    bucket_one = (
        sample_curvature_sensitivity(
            sensitivity_id="curv-branch-001",
            source_row_id="row-curv-branch-001",
            risk_factor="USD-OIS",
            up_shock_amount=21.095478235914463,
            down_shock_amount=152.57198303147396,
            lineage=replace(sample_lineage(), source_row_id="row-curv-branch-001"),
        ),
        sample_curvature_sensitivity(
            sensitivity_id="curv-branch-002",
            source_row_id="row-curv-branch-002",
            risk_factor="USD-LIBOR",
            up_shock_amount=70.03228299171094,
            down_shock_amount=-49.072555279946286,
            lineage=replace(sample_lineage(), source_row_id="row-curv-branch-002"),
        ),
    )
    bucket_two = (
        sample_curvature_sensitivity(
            sensitivity_id="curv-branch-003",
            source_row_id="row-curv-branch-003",
            bucket="2",
            risk_factor="EUR-OIS",
            up_shock_amount=60.0,
            down_shock_amount=30.0,
            lineage=replace(sample_lineage(), source_row_id="row-curv-branch-003"),
        ),
    )

    result = calculate_girr_curvature_risk_class_capital(
        (*bucket_one, *bucket_two),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    by_bucket_scenario = {
        (record.bucket_id, record.scenario): record for record in result.curvature_bucket_branches
    }
    assert by_bucket_scenario[("1", SbmScenarioLabel.LOW)].selected_branch == "down"
    assert by_bucket_scenario[("1", SbmScenarioLabel.MEDIUM)].selected_branch == "down"
    assert by_bucket_scenario[("1", SbmScenarioLabel.HIGH)].selected_branch == "up"
    assert by_bucket_scenario[("2", SbmScenarioLabel.LOW)].selected_branch == "up"
    assert by_bucket_scenario[("2", SbmScenarioLabel.HIGH)].selected_branch == "up"
    assert by_bucket_scenario[("1", SbmScenarioLabel.LOW)].down_bucket_capital > (
        by_bucket_scenario[("1", SbmScenarioLabel.LOW)].up_bucket_capital
    )
    assert by_bucket_scenario[("1", SbmScenarioLabel.HIGH)].up_bucket_capital > (
        by_bucket_scenario[("1", SbmScenarioLabel.HIGH)].down_bucket_capital
    )
    assert result.selected_scenario in {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }
    assert set(result.scenario_totals or {}) == {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }
    assert all(detail.intra_buckets for detail in result.scenario_details)


def test_girr_curvature_engine_applies_psi_and_mar21_5_tie_break() -> None:
    result = calculate_girr_curvature_risk_class_capital(
        (
            sample_curvature_sensitivity(
                sensitivity_id="curv-psi-001",
                source_row_id="row-curv-psi-001",
                risk_factor="USD-OIS",
                up_shock_amount=-1.0,
                down_shock_amount=-2.0,
                lineage=replace(sample_lineage(), source_row_id="row-curv-psi-001"),
            ),
            sample_curvature_sensitivity(
                sensitivity_id="curv-psi-002",
                source_row_id="row-curv-psi-002",
                risk_factor="USD-LIBOR",
                up_shock_amount=-1.0,
                down_shock_amount=-2.0,
                lineage=replace(sample_lineage(), source_row_id="row-curv-psi-002"),
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    low_record = next(
        record
        for record in result.curvature_bucket_branches
        if record.bucket_id == "1" and record.scenario is SbmScenarioLabel.LOW
    )
    assert low_record.up_bucket_capital == 0.0
    assert low_record.down_bucket_capital == 0.0
    assert low_record.selected_branch == "up"
    assert low_record.selected_sum == -2.0
    assert low_record.up_sum > low_record.down_sum
    assert low_record.selected_psi_zero_count == 1
    assert low_record.up_psi_zero_count == 1
    assert low_record.down_psi_zero_count == 1


def test_girr_curvature_audit_serializes_branches_and_numeric_drift_inputs() -> None:
    risk_class = calculate_girr_curvature_risk_class_capital(
        (
            sample_curvature_sensitivity(
                sensitivity_id="curv-audit-001",
                source_row_id="row-curv-audit-001",
                risk_factor="USD-OIS",
                up_shock_amount=-1.0,
                down_shock_amount=-2.0,
                lineage=replace(sample_lineage(), source_row_id="row-curv-audit-001"),
            ),
            sample_curvature_sensitivity(
                sensitivity_id="curv-audit-002",
                source_row_id="row-curv-audit-002",
                risk_factor="USD-LIBOR",
                up_shock_amount=-1.0,
                down_shock_amount=-2.0,
                lineage=replace(sample_lineage(), source_row_id="row-curv-audit-002"),
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )
    payload = serialize_sbm_result(
        SbmCapitalResult(
            total_capital=risk_class.selected_capital,
            risk_classes=(risk_class,),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            profile_hash="a" * 64,
            input_hash="b" * 64,
        )
    )
    risk_payload = payload["risk_classes"][0]

    assert risk_payload["curvature_branches"]
    assert risk_payload["curvature_bucket_branches"][0]["selected_branch"] == "up"
    assert risk_payload["curvature_bucket_branches"][0]["selected_psi_zero_count"] == 1
    drifted_record = replace(
        risk_class.curvature_bucket_branches[0],
        selected_bucket_capital=risk_class.curvature_bucket_branches[0].selected_bucket_capital
        + 0.01,
    )
    drifted_risk_class = replace(
        risk_class,
        curvature_bucket_branches=(drifted_record, *risk_class.curvature_bucket_branches[1:]),
    )
    drifted_payload = serialize_sbm_result(
        SbmCapitalResult(
            total_capital=drifted_risk_class.selected_capital,
            risk_classes=(drifted_risk_class,),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            profile_hash="a" * 64,
            input_hash="b" * 64,
        )
    )
    assert drifted_payload != payload


def test_calculate_sbm_capital_routes_girr_curvature() -> None:
    result = calculate_sbm_capital(
        (sample_curvature_sensitivity(up_shock_amount=12_000.0, down_shock_amount=8_000.0),),
        context=sample_context(),
    )

    assert result.risk_classes[0].risk_class is SbmRiskClass.GIRR
    assert result.risk_classes[0].risk_measure is SbmRiskMeasure.CURVATURE
    assert result.total_capital == pytest.approx(12_000.0)


def test_curvature_capital_unsupported_feature_is_structured() -> None:
    feature = curvature_capital_unsupported_feature(SbmRegulatoryProfile.BASEL_MAR21.value)

    assert feature.feature_key == "sbm_curvature_capital"
    assert feature.dimension == "risk_measure"
    assert feature.requirement_id == CURVATURE_CAPITAL_REQUIREMENT_ID


@pytest.mark.parametrize("risk_class", list(SbmRiskClass))
def test_basel_curvature_support_matrix_includes_every_risk_class(
    risk_class: SbmRiskClass,
) -> None:
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        risk_class,
        SbmRiskMeasure.CURVATURE,
    )


def test_ensure_sbm_capital_paths_supported_accepts_girr_curvature() -> None:
    ensure_sbm_capital_paths_supported(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        (sample_curvature_sensitivity(),),
    )


def test_curvature_risk_weights_are_cited_mar21_98_99_parameters() -> None:
    girr_weight, girr_citations = curvature_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        risk_class=SbmRiskClass.GIRR,
    )
    commodity_weight, commodity_citations = curvature_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        risk_class=SbmRiskClass.COMMODITY,
        bucket_id="4",
    )
    fx_weight, fx_citations = curvature_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        risk_class=SbmRiskClass.FX,
        currency="EUR",
        reporting_currency="USD",
    )

    assert girr_weight == pytest.approx(0.017)
    assert "basel_mar21_99" in girr_citations
    assert commodity_weight == pytest.approx(0.80)
    assert "basel_mar21_99" in commodity_citations
    assert fx_weight == pytest.approx(0.15 / np.sqrt(2.0))
    assert "basel_mar21_98" in fx_citations
    assert "basel_mar21_88" in fx_citations
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="repo rates"):
        curvature_risk_weight(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            risk_class=SbmRiskClass.EQUITY,
            bucket_id="1",
            risk_factor="REPO",
        )


def test_fx_curvature_public_path_uses_squared_inter_bucket_gamma() -> None:
    result = calculate_sbm_capital(
        (
            sample_curvature_sensitivity(
                sensitivity_id="fx-curv-001",
                source_row_id="row-fx-curv-001",
                risk_class=SbmRiskClass.FX,
                bucket="EUR",
                risk_factor="EUR",
                tenor=None,
                amount_currency="USD",
                up_shock_amount=100.0,
                down_shock_amount=40.0,
                lineage=replace(sample_lineage(), source_row_id="row-fx-curv-001"),
            ),
            sample_curvature_sensitivity(
                sensitivity_id="fx-curv-002",
                source_row_id="row-fx-curv-002",
                risk_class=SbmRiskClass.FX,
                bucket="GBP",
                risk_factor="GBP",
                tenor=None,
                amount_currency="USD",
                up_shock_amount=200.0,
                down_shock_amount=80.0,
                lineage=replace(sample_lineage(), source_row_id="row-fx-curv-002"),
            ),
        ),
        context=sample_context(),
    )

    risk_class = result.risk_classes[0]
    medium = next(
        detail
        for detail in risk_class.scenario_details
        if detail.scenario is SbmScenarioLabel.MEDIUM
    )
    assert risk_class.risk_class is SbmRiskClass.FX
    assert risk_class.risk_measure is SbmRiskMeasure.CURVATURE
    assert medium.inter_bucket_correlations == (("EUR", "GBP", pytest.approx(0.36)),)


def test_fx_curvature_cross_pair_scalar_marker_divides_cvr_charges() -> None:
    result = calculate_curvature_risk_class_capital(
        (
            sample_curvature_sensitivity(
                sensitivity_id="fx-cross-curv-001",
                source_row_id="row-fx-cross-curv-001",
                risk_class=SbmRiskClass.FX,
                bucket="EUR",
                risk_factor="EUR",
                qualifier="EUR/GBP",
                tenor=None,
                up_shock_amount=150.0,
                down_shock_amount=60.0,
                mapping_citation_ids=(FX_CURVATURE_SCALAR_1_5_FLAG,),
                lineage=replace(sample_lineage(), source_row_id="row-fx-cross-curv-001"),
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert result.risk_class is SbmRiskClass.FX
    assert result.buckets[0].kb == pytest.approx(100.0)
    assert result.buckets[0].weighted_sensitivities[0].scaled_amount == pytest.approx(100.0)


def test_fx_curvature_cross_pair_scalar_rejects_uncited_pair_context() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="two-currency qualifier"):
        calculate_curvature_risk_class_capital(
            (
                sample_curvature_sensitivity(
                    sensitivity_id="fx-cross-curv-001",
                    source_row_id="row-fx-cross-curv-001",
                    risk_class=SbmRiskClass.FX,
                    bucket="EUR",
                    risk_factor="EUR",
                    qualifier=None,
                    tenor=None,
                    up_shock_amount=150.0,
                    down_shock_amount=60.0,
                    mapping_citation_ids=(FX_CURVATURE_SCALAR_1_5_FLAG,),
                    lineage=replace(sample_lineage(), source_row_id="row-fx-cross-curv-001"),
                ),
            ),
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            reporting_currency="USD",
        )


def test_csr_nonsec_curvature_uses_name_only_squared_correlation() -> None:
    result = calculate_curvature_risk_class_capital(
        (
            sample_curvature_sensitivity(
                sensitivity_id="csr-curv-001",
                source_row_id="row-csr-curv-001",
                risk_class=SbmRiskClass.CSR_NONSEC,
                bucket="11",
                risk_factor="BOND",
                qualifier="issuer-a",
                tenor=None,
                up_shock_amount=10.0,
                down_shock_amount=4.0,
                lineage=replace(sample_lineage(), source_row_id="row-csr-curv-001"),
            ),
            sample_curvature_sensitivity(
                sensitivity_id="csr-curv-002",
                source_row_id="row-csr-curv-002",
                risk_class=SbmRiskClass.CSR_NONSEC,
                bucket="11",
                risk_factor="CDS",
                qualifier="issuer-b",
                tenor=None,
                up_shock_amount=20.0,
                down_shock_amount=6.0,
                lineage=replace(sample_lineage(), source_row_id="row-csr-curv-002"),
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    medium = next(
        detail for detail in result.scenario_details if detail.scenario is SbmScenarioLabel.MEDIUM
    )
    pairwise = medium.intra_buckets[0].pairwise_correlations
    off_diagonal = next(
        record for record in pairwise if record.sensitivity_a != record.sensitivity_b
    )

    assert off_diagonal.correlation == pytest.approx(0.35**2)
    assert "basel_mar21_100" in medium.intra_buckets[0].citation_ids
