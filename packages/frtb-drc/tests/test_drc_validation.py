from __future__ import annotations

import math

import pytest
from frtb_drc import (
    BASEL_MAR22_PROFILE_ID,
    CreditQuality,
    DefaultDirection,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    validate_position,
    validate_positions,
)


def test_validate_position_accepts_valid_non_securitisation_position() -> None:
    position = _position()

    assert validate_position(position) is position


def test_validate_positions_rejects_duplicate_position_ids() -> None:
    first = _position(position_id="pos-1")
    second = _position(
        position_id="pos-1",
        source_row_id="row-2",
        lineage=DrcSourceLineage(
            source_system="test",
            source_file="positions.csv",
            source_row_id="row-2",
        ),
    )

    with pytest.raises(DrcInputError, match="duplicate position_id"):
        validate_positions((first, second))


@pytest.mark.parametrize(
    ("field_name", "override", "message"),
    [
        ("position_id", {"position_id": ""}, "position_id must be non-empty"),
        ("source_row_id", {"source_row_id": "  "}, "source_row_id must be non-empty"),
        ("desk_id", {"desk_id": ""}, "desk_id must be non-empty"),
        ("legal_entity", {"legal_entity": ""}, "legal_entity must be non-empty"),
        ("currency", {"currency": ""}, "currency must be non-empty"),
        ("bucket_key", {"bucket_key": None}, "bucket_key must be non-empty"),
    ],
)
def test_validate_position_rejects_missing_identity_fields(
    field_name: str,
    override: dict[str, object],
    message: str,
) -> None:
    assert field_name

    with pytest.raises(DrcInputError, match=message):
        validate_position(_position(**override))


def test_validate_position_rejects_missing_lineage() -> None:
    with pytest.raises(DrcInputError, match="lineage is required"):
        validate_position(_position(lineage=None))


def test_validate_position_rejects_missing_citation_ids() -> None:
    with pytest.raises(DrcInputError, match="citation_ids must contain at least one citation"):
        validate_position(_position(citation_ids=()))


@pytest.mark.parametrize("citation_ids", [("",), ("  ",)])
def test_validate_position_rejects_blank_citation_ids(citation_ids: tuple[str, ...]) -> None:
    with pytest.raises(DrcInputError, match="citation_ids must contain non-empty citations"):
        validate_position(_position(citation_ids=citation_ids))


def test_validate_position_rejects_unsupported_citation_policy() -> None:
    with pytest.raises(DrcInputError, match="unsupported citation_policy"):
        validate_position(_position(), citation_policy="permissive")


def test_validate_position_rejects_incomplete_lineage() -> None:
    lineage = DrcSourceLineage(
        source_system="test",
        source_file="",
        source_row_id="row-1",
    )

    with pytest.raises(DrcInputError, match=r"lineage\.source_file must be non-empty"):
        validate_position(_position(lineage=lineage))


def test_validate_position_rejects_conflicting_source_row_lineage() -> None:
    lineage = DrcSourceLineage(
        source_system="test",
        source_file="positions.csv",
        source_row_id="row-2",
    )

    with pytest.raises(
        DrcInputError,
        match=r"source_row_id must match lineage\.source_row_id",
    ):
        validate_position(_position(source_row_id="row-1", lineage=lineage))


def test_validate_position_rejects_non_finite_amounts() -> None:
    with pytest.raises(DrcInputError, match="notional must be finite"):
        validate_position(_position(notional=math.inf))

    with pytest.raises(DrcInputError, match="market_value must be finite"):
        validate_position(_position(market_value=math.nan))


def test_validate_position_rejects_negative_maturity() -> None:
    with pytest.raises(DrcInputError, match="maturity_years must be non-negative"):
        validate_position(_position(maturity_years=-0.1))


def test_validate_position_rejects_invalid_lgd_override() -> None:
    with pytest.raises(DrcInputError, match="lgd_override must be between 0 and 1"):
        validate_position(_position(lgd_override=1.1))


def test_validate_position_rejects_non_securitisation_without_issuer() -> None:
    with pytest.raises(DrcInputError, match="issuer_id must be non-empty"):
        validate_position(_position(issuer_id=None))


def test_validate_position_rejects_non_securitisation_without_seniority() -> None:
    with pytest.raises(DrcInputError, match="seniority is required"):
        validate_position(_position(seniority=None))


def test_validate_position_rejects_unrated_non_securitisation_credit_quality() -> None:
    with pytest.raises(
        DrcInputError,
        match=r"UNRATED.*not a chargeable.*US_NPR_2_0",
    ):
        validate_position(_position(credit_quality=CreditQuality.UNRATED))


def test_validate_position_accepts_basel_unrated_credit_quality() -> None:
    position = _position(
        bucket_key="SOVEREIGN",
        credit_quality=CreditQuality.UNRATED,
        citation_ids=("BASEL_MAR22_24",),
    )

    assert validate_position(position, profile_id=BASEL_MAR22_PROFILE_ID) is position


@pytest.mark.parametrize(
    "bucket_key",
    ["US_SOVEREIGN", "SPECIFIED_SUPRANATIONAL", "MDB", "MUNICIPAL", " CORPORATE "],
)
def test_validate_position_rejects_non_chargeable_nonsec_bucket_keys(bucket_key: str) -> None:
    with pytest.raises(
        DrcInputError,
        match=r"not a chargeable.*US_NPR_2_0",
    ):
        validate_position(_position(bucket_key=bucket_key))


def test_validate_position_rejects_us_bucket_under_basel_profile() -> None:
    with pytest.raises(DrcInputError, match="NON_US_SOVEREIGN"):
        validate_position(
            _position(
                bucket_key="NON_US_SOVEREIGN",
                credit_quality=CreditQuality.AA,
                citation_ids=("BASEL_MAR22_22",),
            ),
            profile_id=BASEL_MAR22_PROFILE_ID,
        )


def test_validate_position_rejects_securitisation_without_tranche() -> None:
    position = _position(
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        instrument_type=DrcInstrumentType.SECURITISATION_TRANCHE,
        issuer_id="issuer-a",
        tranche_id=None,
        seniority=None,
    )

    with pytest.raises(DrcInputError, match="tranche_id must be non-empty"):
        validate_position(position)


def test_validate_position_rejects_ctp_without_tranche_index_series_or_issuer() -> None:
    position = _position(
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        instrument_type=DrcInstrumentType.INDEX_TRANCHE,
        issuer_id=None,
        tranche_id=None,
        index_series_id=None,
        seniority=None,
    )

    with pytest.raises(
        DrcInputError,
        match="CTP positions require tranche_id, index_series_id, or issuer_id",
    ):
        validate_position(position)


def test_position_construction_rejects_implicit_direction() -> None:
    with pytest.raises(ValueError, match="default_direction must be one of"):
        _position(default_direction="")


def _position(**overrides: object) -> DrcPosition:
    values: dict[str, object] = {
        "position_id": "pos-1",
        "source_row_id": "row-1",
        "desk_id": "desk-a",
        "legal_entity": "bank-na",
        "risk_class": DrcRiskClass.NON_SECURITISATION,
        "instrument_type": DrcInstrumentType.BOND,
        "default_direction": DefaultDirection.LONG,
        "issuer_id": "issuer-a",
        "tranche_id": None,
        "index_series_id": None,
        "bucket_key": "CORPORATE",
        "seniority": DrcSeniority.SENIOR_DEBT,
        "credit_quality": "INVESTMENT_GRADE",
        "notional": 100.0,
        "market_value": 99.0,
        "cumulative_pnl": 0.0,
        "maturity_years": 1.0,
        "currency": "USD",
        "lineage": DrcSourceLineage(
            source_system="test",
            source_file="positions.csv",
            source_row_id="row-1",
        ),
        "citation_ids": ("US_NPR_210_SCOPE",),
    }
    values.update(overrides)
    return DrcPosition(**values)  # type: ignore[arg-type]
