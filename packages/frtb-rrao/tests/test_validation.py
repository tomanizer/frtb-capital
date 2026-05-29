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
    normalise_gross_effective_notional,
    validate_rrao_positions,
)


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


def assert_rejects(position: RraoPosition, match: str) -> None:
    with pytest.raises(RraoInputError, match=match):
        validate_rrao_positions((position,))


def test_validate_rrao_positions_accepts_valid_canonical_inputs() -> None:
    positions = validate_rrao_positions((sample_position(),))

    assert positions == (sample_position(),)


def test_validate_rrao_positions_rejects_single_position_instead_of_iterable() -> None:
    with pytest.raises(RraoInputError, match="iterable"):
        validate_rrao_positions(sample_position())


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("position_id", "non-empty text"),
        ("source_row_id", "non-empty text"),
        ("desk_id", "non-empty text"),
        ("legal_entity", "non-empty text"),
        ("currency", "non-empty text"),
        ("evidence_label", "non-empty text"),
        ("notional_source", "non-empty text"),
    ],
)
def test_validate_rrao_positions_rejects_missing_identity_and_evidence(
    field: str,
    message: str,
) -> None:
    assert_rejects(sample_position(**{field: ""}), message)


def test_validate_rrao_positions_rejects_missing_lineage() -> None:
    assert_rejects(sample_position(lineage=None), "source lineage is required")


def test_validate_rrao_positions_rejects_invalid_lineage_fields() -> None:
    lineage = replace(sample_lineage(), source_system="")

    assert_rejects(sample_position(lineage=lineage), "lineage.source_system")


def test_validate_rrao_positions_rejects_invalid_lineage_column_map() -> None:
    lineage = replace(sample_lineage(), source_column_map=(("RiskType",),))  # type: ignore[arg-type]

    assert_rejects(sample_position(lineage=lineage), "source column map")


def test_validate_rrao_positions_rejects_duplicate_position_ids() -> None:
    duplicate = sample_position(source_row_id="row-002")

    with pytest.raises(RraoInputError, match="duplicate position id"):
        validate_rrao_positions((sample_position(), duplicate))


@pytest.mark.parametrize("notional", [-1.0, math.inf, -math.inf, math.nan])
def test_validate_rrao_positions_rejects_invalid_gross_effective_notional(notional: float) -> None:
    assert_rejects(
        sample_position(gross_effective_notional=notional), "gross effective notional|finite"
    )


def test_validate_rrao_positions_rejects_invalid_enum_values() -> None:
    assert_rejects(sample_position(evidence_type="EXOTIC_UNDERLYING"), "invalid evidence type")
    assert_rejects(sample_position(classification_hint="EXOTIC"), "invalid classification hint")
    assert_rejects(sample_position(exclusion_reason="LISTED"), "invalid exclusion reason")


def test_validate_rrao_positions_rejects_unsupported_classification_paths() -> None:
    assert_rejects(
        sample_position(classification_hint=RraoClassification.UNSUPPORTED),
        "unsupported classification path",
    )
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
            is_investment_fund_exposure=True,
        ),
        "investment fund descriptor",
    )
    assert_rejects(
        sample_position(is_investment_fund_exposure=True),
        "investment-fund evidence type",
    )


def test_validate_rrao_positions_requires_supervisor_directive_evidence() -> None:
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
            classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
        ),
        "supervisor_directive_id",
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
    )
    assert_rejects(
        sample_position(
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            exclusion_reason=RraoExclusionReason.LISTED,
        ),
        "exclusion_evidence_id",
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


def test_validate_rrao_positions_rejects_invalid_optional_fields() -> None:
    assert_rejects(sample_position(underlying_count=-1), "underlying count")
    assert_rejects(sample_position(is_path_dependent="yes"), "is_path_dependent")
    assert_rejects(sample_position(is_ctp_hedge="no"), "is_ctp_hedge")
    assert_rejects(sample_position(citations=("",)), "citations")


def test_normalise_gross_effective_notional_uses_explicit_sign_convention() -> None:
    assert normalise_gross_effective_notional(25.0) == 25.0
    assert (
        normalise_gross_effective_notional(-25.0, source_sign_convention="signed_absolute") == 25.0
    )

    with pytest.raises(RraoInputError, match="non-negative"):
        normalise_gross_effective_notional(-25.0)
    with pytest.raises(RraoInputError, match="source_sign_convention"):
        normalise_gross_effective_notional(25.0, source_sign_convention="net")  # type: ignore[arg-type]
