from __future__ import annotations

import math
from dataclasses import replace
from datetime import date

import pytest
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    coerce_risk_class,
    coerce_sign_convention,
    normalise_currency_code,
    normalise_sensitivity_amount,
    sensitivity_sort_key,
    sort_sensitivities_deterministic,
    validate_sbm_calculation_context,
    validate_sbm_sensitivities,
)


def sample_lineage() -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id="row-001",
        source_column_map=(
            ("RiskType", "risk_class"),
            ("AmountUSD", "amount"),
        ),
    )


def sample_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "sens-001",
        "source_row_id": "row-001",
        "desk_id": "rates-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.GIRR,
        "risk_measure": SbmRiskMeasure.DELTA,
        "bucket": "1",
        "risk_factor": "USD",
        "amount": 1_000_000.0,
        "amount_currency": "USD",
        "tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_lineage(),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def sample_context(**overrides: object) -> SbmCalculationContext:
    fields = {
        "run_id": "run-001",
        "calculation_date": date(2026, 5, 30),
        "base_currency": "USD",
        "reporting_currency": "USD",
        "profile_id": SbmRegulatoryProfile.US_NPR_2_0.value,
    }
    fields.update(overrides)
    return SbmCalculationContext(**fields)  # type: ignore[arg-type]


def assert_rejects(
    sensitivity: SbmSensitivity,
    match: str,
    *,
    expected_field: str | None = None,
    expected_sensitivity_id: str | None = "sens-001",
) -> None:
    with pytest.raises(SbmInputError, match=match) as exc_info:
        validate_sbm_sensitivities((sensitivity,))
    if expected_field is not None:
        assert exc_info.value.field == expected_field
    if expected_sensitivity_id is not None:
        assert exc_info.value.sensitivity_id == expected_sensitivity_id


def test_validate_sbm_sensitivities_accepts_valid_canonical_inputs() -> None:
    sensitivities = validate_sbm_sensitivities((sample_sensitivity(),))

    assert sensitivities == (sample_sensitivity(),)


def test_validate_sbm_sensitivities_rejects_single_sensitivity_instead_of_iterable() -> None:
    with pytest.raises(SbmInputError, match="iterable"):
        validate_sbm_sensitivities(sample_sensitivity())


def test_validate_sbm_sensitivities_rejects_non_sensitivity_members() -> None:
    with pytest.raises(SbmInputError, match="only SbmSensitivity objects"):
        validate_sbm_sensitivities((object(),))


@pytest.mark.parametrize(
    ("field", "message", "expected_sensitivity_id"),
    [
        ("sensitivity_id", "non-empty text", ""),
        ("source_row_id", "non-empty text", "sens-001"),
        ("desk_id", "non-empty text", "sens-001"),
        ("legal_entity", "non-empty text", "sens-001"),
        ("bucket", "non-empty text", "sens-001"),
        ("risk_factor", "non-empty text", "sens-001"),
    ],
)
def test_validate_sbm_sensitivities_rejects_missing_identity_fields(
    field: str,
    message: str,
    expected_sensitivity_id: str,
) -> None:
    assert_rejects(
        sample_sensitivity(**{field: ""}),
        message,
        expected_field=field,
        expected_sensitivity_id=expected_sensitivity_id,
    )


def test_validate_sbm_sensitivities_rejects_duplicate_sensitivity_id() -> None:
    with pytest.raises(SbmInputError, match="duplicate sensitivity id") as exc_info:
        validate_sbm_sensitivities((sample_sensitivity(), sample_sensitivity()))
    assert exc_info.value.field == "sensitivity_id"


def test_validate_sbm_sensitivities_rejects_non_finite_amount() -> None:
    assert_rejects(sample_sensitivity(amount=math.inf), "finite", expected_field="amount")


def test_validate_sbm_sensitivities_rejects_invalid_currency_code() -> None:
    assert_rejects(
        sample_sensitivity(amount_currency="US"),
        "three-letter",
        expected_field="amount_currency",
    )


def test_validate_sbm_sensitivities_rejects_unknown_enum_values() -> None:
    assert_rejects(
        sample_sensitivity(risk_class="UNKNOWN"),
        "risk_class must be one of",
        expected_field="risk_class",
    )
    assert_rejects(
        sample_sensitivity(risk_measure="SPREAD"),
        "risk_measure must be one of",
        expected_field="risk_measure",
    )
    assert_rejects(
        sample_sensitivity(sign_convention="BUY"),
        "sign_convention must be one of",
        expected_field="sign_convention",
    )


def test_validate_sbm_sensitivities_rejects_missing_lineage() -> None:
    assert_rejects(
        sample_sensitivity(lineage=None),  # type: ignore[arg-type]
        "invalid source lineage",
        expected_field="lineage",
    )


def test_validate_sbm_sensitivities_rejects_source_row_id_mismatch() -> None:
    assert_rejects(
        sample_sensitivity(source_row_id="row-002"),
        "source_row_id must match lineage.source_row_id",
        expected_field="source_row_id",
    )


def test_validate_sbm_sensitivities_requires_girr_tenor_for_delta() -> None:
    assert_rejects(
        sample_sensitivity(tenor=None),
        "non-empty text",
        expected_field="tenor",
    )


def test_validate_sbm_sensitivities_requires_csr_qualifier() -> None:
    assert_rejects(
        sample_sensitivity(
            risk_class=SbmRiskClass.CSR_NONSEC,
            qualifier=None,
            tenor=None,
        ),
        "qualifier is required",
        expected_field="qualifier",
    )


def test_validate_sbm_sensitivities_requires_curvature_shock_amounts() -> None:
    assert_rejects(
        sample_sensitivity(
            risk_measure=SbmRiskMeasure.CURVATURE,
            tenor=None,
            up_shock_amount=None,
            down_shock_amount=None,
        ),
        "curvature inputs require",
        expected_field="up_shock_amount",
    )


def test_validate_sbm_calculation_context_rejects_unknown_profile() -> None:
    with pytest.raises(SbmInputError, match="profile_id must be one of") as exc_info:
        validate_sbm_calculation_context(sample_context(profile_id="UNKNOWN"))
    assert exc_info.value.field == "profile_id"


def test_normalisation_helpers_coerce_enums_and_currency() -> None:
    assert normalise_sensitivity_amount(-1_000.0) == -1_000.0
    assert normalise_currency_code("usd") == "USD"
    assert coerce_risk_class("GIRR") is SbmRiskClass.GIRR
    assert coerce_sign_convention("LONG") is SbmSignConvention.LONG


def test_sort_sensitivities_deterministic_orders_by_risk_class_bucket_and_id() -> None:
    second = sample_sensitivity(
        sensitivity_id="sens-002",
        source_row_id="row-002",
        bucket="2",
        lineage=replace(sample_lineage(), source_row_id="row-002"),
    )
    fx = sample_sensitivity(
        sensitivity_id="sens-003",
        source_row_id="row-003",
        risk_class=SbmRiskClass.FX,
        bucket="USD",
        risk_factor="EUR",
        tenor=None,
        lineage=replace(sample_lineage(), source_row_id="row-003"),
    )
    ordered = sort_sensitivities_deterministic((fx, second, sample_sensitivity()))

    assert [item.sensitivity_id for item in ordered] == ["sens-003", "sens-001", "sens-002"]
    assert sensitivity_sort_key(sample_sensitivity()) == ("GIRR", "DELTA", "1", "USD", "sens-001")
