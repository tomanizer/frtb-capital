from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
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
    calculate_sbm_capital,
    curvature_capital_unsupported_feature,
    curvature_worst_branch,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_curvature_capital_unsupported,
    ensure_sbm_risk_class_measure_supported,
    parse_curvature_input,
    validate_curvature_sensitivities,
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


def test_ensure_sbm_curvature_capital_unsupported_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match=CURVATURE_CAPITAL_REQUIREMENT_ID):
        ensure_sbm_curvature_capital_unsupported(SbmRegulatoryProfile.BASEL_MAR21.value)


def test_ensure_sbm_curvature_capital_unsupported_validates_inputs_first() -> None:
    with pytest.raises(SbmInputError, match="curvature inputs require"):
        ensure_sbm_curvature_capital_unsupported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            (sample_curvature_sensitivity(up_shock_amount=None),),
        )


def test_curvature_capital_unsupported_feature_is_structured() -> None:
    feature = curvature_capital_unsupported_feature(SbmRegulatoryProfile.BASEL_MAR21.value)

    assert feature.feature_key == "sbm_curvature_capital"
    assert feature.dimension == "risk_measure"
    assert feature.requirement_id == CURVATURE_CAPITAL_REQUIREMENT_ID


@pytest.mark.parametrize("risk_class", list(SbmRiskClass))
def test_basel_curvature_capital_paths_fail_closed(risk_class: SbmRiskClass) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            risk_class,
            SbmRiskMeasure.CURVATURE,
        )


def test_calculate_sbm_capital_rejects_curvature_without_placeholder_totals() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
        calculate_sbm_capital(
            (sample_curvature_sensitivity(),),
            context=sample_context(),
        )


def test_ensure_sbm_capital_paths_supported_reports_curvature_dimension() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="validate_curvature_sensitivities"):
        ensure_sbm_capital_paths_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            (sample_curvature_sensitivity(),),
        )
