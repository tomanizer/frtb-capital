from __future__ import annotations

import math
from dataclasses import replace

import pytest
from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoPosition,
    RraoSourceLineage,
    validate_rrao_positions,
)
from frtb_rrao.validation import normalise_gross_effective_notional


def sample_lineage() -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id="row-001",
        source_column_map=(
            ("RiskType", "evidence_type"),
            ("AmountUSD", "gross_effective_notional"),
        ),
    )


def sample_position(**overrides: object) -> RraoPosition:
    fields = {
        "position_id": "pos-001",
        "source_row_id": "row-001",
        "desk_id": "rates-exotics",
        "legal_entity": "LE-001",
        "gross_effective_notional": 1_000_000.0,
        "currency": "USD",
        "evidence_type": RraoEvidenceType.EXOTIC_UNDERLYING,
        "evidence_label": "weather derivative",
        "classification_hint": RraoClassification.EXOTIC,
        "lineage": sample_lineage(),
    }
    fields.update(overrides)
    return RraoPosition(**fields)  # type: ignore[arg-type]


def assert_rejects(
    position: RraoPosition,
    match: str,
    *,
    expected_field: str | None = None,
    expected_position_id: str | None = "pos-001",
) -> None:
    with pytest.raises(RraoInputError, match=match) as exc_info:
        validate_rrao_positions((position,))
    if expected_field is not None:
        assert exc_info.value.field == expected_field
    if expected_position_id is not None:
        assert exc_info.value.position_id == expected_position_id


def test_validate_rrao_positions_accepts_valid_canonical_inputs() -> None:
    positions = validate_rrao_positions((sample_position(),))

    assert positions == (sample_position(),)


def test_validate_rrao_positions_rejects_single_position_instead_of_iterable() -> None:
    with pytest.raises(RraoInputError, match="iterable"):
        validate_rrao_positions(sample_position())


def test_validate_rrao_positions_rejects_non_position_members() -> None:
    with pytest.raises(RraoInputError, match="only RraoPosition objects"):
        validate_rrao_positions((object(),))


@pytest.mark.parametrize(
    ("field", "message", "expected_position_id"),
    [
        ("position_id", "non-empty text", ""),
        ("source_row_id", "non-empty text", "pos-001"),
        ("desk_id", "non-empty text", "pos-001"),
        ("legal_entity", "non-empty text", "pos-001"),
        ("currency", "non-empty text", "pos-001"),
        ("evidence_label", "non-empty text", "pos-001"),
        ("notional_source", "non-empty text", "pos-001"),
    ],
)
def test_validate_rrao_positions_rejects_missing_identity_and_evidence(
    field: str,
    message: str,
    expected_position_id: str,
) -> None:
    assert_rejects(
        sample_position(**{field: ""}),
        message,
        expected_field=field,
        expected_position_id=expected_position_id,
    )


def test_validate_rrao_positions_rejects_missing_lineage() -> None:
    assert_rejects(
        sample_position(lineage=None),
        "source lineage is required",
        expected_field="lineage",
    )


@pytest.mark.parametrize(
    ("lineage", "match", "expected_field"),
    [
        (object(), "invalid source lineage", "lineage"),
        (
            replace(sample_lineage(), source_system=""),
            "lineage.source_system",
            "lineage.source_system",
        ),
        (
            replace(sample_lineage(), source_file=""),
            "lineage.source_file",
            "lineage.source_file",
        ),
        (
            replace(sample_lineage(), source_row_id=""),
            "lineage.source_row_id",
            "lineage.source_row_id",
        ),
        (
            replace(sample_lineage(), source_column_map=(("RiskType",),)),  # type: ignore[arg-type]
            "source column map",
            "lineage.source_column_map",
        ),
        (
            replace(sample_lineage(), source_column_map=(("", "evidence_type"),)),
            "lineage.source_column_map.source",
            "lineage.source_column_map.source",
        ),
        (
            replace(sample_lineage(), source_column_map=(("RiskType", ""),)),
            "lineage.source_column_map.canonical",
            "lineage.source_column_map.canonical",
        ),
    ],
)
def test_validate_rrao_positions_rejects_invalid_lineage_fields(
    lineage: object,
    match: str,
    expected_field: str,
) -> None:
    assert_rejects(
        sample_position(lineage=lineage),
        match,
        expected_field=expected_field,
    )


def test_validate_rrao_positions_rejects_duplicate_position_ids() -> None:
    duplicate = sample_position(source_row_id="row-002")

    with pytest.raises(RraoInputError, match="duplicate position id") as exc_info:
        validate_rrao_positions((sample_position(), duplicate))
    assert exc_info.value.field == "position_id"
    assert exc_info.value.position_id == "pos-001"


@pytest.mark.parametrize("notional", [-1.0, math.inf, -math.inf, math.nan])
def test_validate_rrao_positions_rejects_invalid_gross_effective_notional(notional: float) -> None:
    assert_rejects(
        sample_position(gross_effective_notional=notional),
        "gross effective notional|finite",
        expected_field="gross_effective_notional",
        expected_position_id="",
    )


def test_validate_rrao_positions_rejects_invalid_enum_values() -> None:
    assert_rejects(
        sample_position(evidence_type="EXOTIC_UNDERLYING"),
        "invalid evidence type",
        expected_field="evidence_type",
    )
    assert_rejects(
        sample_position(classification_hint="EXOTIC"),
        "invalid classification hint",
        expected_field="classification_hint",
    )
    assert_rejects(
        sample_position(exclusion_reason="LISTED"),
        "invalid exclusion reason",
        expected_field="exclusion_reason",
    )


def test_validate_rrao_positions_rejects_unsupported_classification_paths() -> None:
    assert_rejects(
        sample_position(classification_hint=RraoClassification.UNSUPPORTED),
        "unsupported classification path",
        expected_field="classification_hint",
    )
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
            is_investment_fund_exposure=True,
        ),
        "investment fund descriptor",
        expected_field="investment_fund_descriptor",
    )
    assert_rejects(
        sample_position(is_investment_fund_exposure=True),
        "investment-fund evidence type",
        expected_field="evidence_type",
    )


def test_validate_rrao_positions_requires_supervisor_directive_evidence() -> None:
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
        ),
        "supervisor_directive_id",
        expected_field="supervisor_directive_id",
    )
    assert_rejects(
        sample_position(
            classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
        ),
        "supervisor_directive_id",
        expected_field="supervisor_directive_id",
    )

    validate_rrao_positions(
        (
            sample_position(
                evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
                classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
                supervisor_directive_id="agency-letter-001",
            ),
        )
    )


def test_validate_rrao_positions_requires_exclusion_evidence() -> None:
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
        ),
        "exclusion reason",
        expected_field="exclusion_reason",
    )
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            exclusion_reason=RraoExclusionReason.LISTED,
        ),
        "exclusion_evidence_id",
        expected_field="exclusion_evidence_id",
    )
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            exclusion_reason=RraoExclusionReason.LISTED,
            exclusion_evidence_id="",
        ),
        "exclusion_evidence_id",
        expected_field="exclusion_evidence_id",
    )

    validate_rrao_positions(
        (
            sample_position(
                evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
                classification_hint=RraoClassification.EXCLUDED,
                exclusion_reason=RraoExclusionReason.LISTED,
                exclusion_evidence_id="exchange-listing-001",
            ),
        )
    )


def test_validate_rrao_positions_rejects_exclusion_reason_without_exclusion_evidence_type() -> None:
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.GAP_RISK,
            classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            exclusion_reason=RraoExclusionReason.LISTED,
            exclusion_evidence_id="exchange-listing-001",
        ),
        "explicit exclusion evidence type",
        expected_field="evidence_type",
    )


@pytest.mark.parametrize(
    ("override", "match", "expected_field"),
    [
        ({"underlying_count": "3"}, "underlying count", "underlying_count"),
        ({"underlying_count": True}, "underlying count", "underlying_count"),
        ({"underlying_count": -1}, "underlying count", "underlying_count"),
        ({"is_path_dependent": "yes"}, "is_path_dependent", "is_path_dependent"),
        ({"has_maturity": 1}, "has_maturity", "has_maturity"),
        ({"has_strike_or_barrier": 1}, "has_strike_or_barrier", "has_strike_or_barrier"),
        (
            {"has_multiple_strikes_or_barriers": 1},
            "has_multiple_strikes_or_barriers",
            "has_multiple_strikes_or_barriers",
        ),
        ({"is_ctp_hedge": "no"}, "is_ctp_hedge", "is_ctp_hedge"),
        (
            {"is_investment_fund_exposure": "no"},
            "is_investment_fund_exposure",
            "is_investment_fund_exposure",
        ),
        ({"citations": ("",)}, "citations", "citations"),
    ],
)
def test_validate_rrao_positions_rejects_invalid_optional_fields(
    override: dict[str, object],
    match: str,
    expected_field: str,
) -> None:
    assert_rejects(
        sample_position(**override),
        match,
        expected_field=expected_field,
    )


def test_normalise_gross_effective_notional_uses_explicit_sign_convention() -> None:
    assert normalise_gross_effective_notional(25.0) == 25.0
    assert (
        normalise_gross_effective_notional(-25.0, source_sign_convention="signed_absolute") == 25.0
    )

    with pytest.raises(RraoInputError, match="non-negative"):
        normalise_gross_effective_notional(-25.0)
    with pytest.raises(RraoInputError, match="source_sign_convention"):
        normalise_gross_effective_notional(25.0, source_sign_convention="net")  # type: ignore[arg-type]
