"""Tests for shared risk-factor identifier and metadata primitives."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from frtb_common import (
    BucketId,
    CurrencyCode,
    RiskFactorId,
    RiskFactorLineageId,
    RiskFactorMappingVersion,
    RiskFactorPrimitiveError,
    RiskFactorRiskClassCode,
    RiskFactorTypeCode,
    SensitivityTypeCode,
    Tenor,
)


def test_risk_factor_id_normalises_edges_and_preserves_case() -> None:
    risk_factor_id = RiskFactorId("  SBM:GIRR/USD-OIS.5Y  ")

    assert risk_factor_id.value == "SBM:GIRR/USD-OIS.5Y"
    assert str(risk_factor_id) == "SBM:GIRR/USD-OIS.5Y"
    assert RiskFactorId(str(risk_factor_id)) == risk_factor_id
    assert RiskFactorId("RF:A") < RiskFactorId("RF:B")
    assert RiskFactorId("RF:USD") != RiskFactorId("rf:usd")


@pytest.mark.parametrize(
    "value",
    ["", "   ", "RF USD", "RF#USD", "_leading-marker", ".leading-marker"],
)
def test_risk_factor_id_rejects_unstable_values(value: str) -> None:
    with pytest.raises(RiskFactorPrimitiveError, match="risk_factor_id"):
        RiskFactorId(value)


def test_risk_factor_id_is_immutable() -> None:
    risk_factor_id = RiskFactorId("RF:USD")

    with pytest.raises(FrozenInstanceError):
        risk_factor_id.value = "RF:EUR"


def test_mapping_and_lineage_ids_use_same_stable_identifier_contract() -> None:
    mapping_version = RiskFactorMappingVersion("  RF-TAXONOMY:2026.03  ")
    lineage_id = RiskFactorLineageId("risk-engine/source-row-001")

    assert mapping_version.value == "RF-TAXONOMY:2026.03"
    assert str(lineage_id) == "risk-engine/source-row-001"
    with pytest.raises(RiskFactorPrimitiveError, match="risk_factor_mapping_version"):
        RiskFactorMappingVersion("taxonomy 2026")


def test_bucket_id_is_an_opaque_case_preserved_identifier() -> None:
    assert BucketId("  bucket-12  ").value == "bucket-12"
    assert BucketId("bucket-12") != BucketId("BUCKET-12")


@pytest.mark.parametrize(
    ("primitive", "raw", "expected"),
    [
        (RiskFactorRiskClassCode, " girr ", "GIRR"),
        (RiskFactorRiskClassCode, "csr_non_sec", "CSR_NON_SEC"),
        (RiskFactorTypeCode, " delta ", "DELTA"),
        (SensitivityTypeCode, "vega.option", "VEGA.OPTION"),
    ],
)
def test_metadata_codes_are_uppercase_carrier_tokens(
    primitive: type[RiskFactorRiskClassCode | RiskFactorTypeCode | SensitivityTypeCode],
    raw: str,
    expected: str,
) -> None:
    assert primitive(raw).value == expected


@pytest.mark.parametrize(
    "primitive", [RiskFactorRiskClassCode, RiskFactorTypeCode, SensitivityTypeCode]
)
def test_metadata_codes_reject_whitespace(
    primitive: type[RiskFactorRiskClassCode | RiskFactorTypeCode | SensitivityTypeCode],
) -> None:
    with pytest.raises(RiskFactorPrimitiveError, match="whitespace"):
        primitive("CSR NON SEC")


def test_currency_code_normalises_uppercase_and_validates_shape() -> None:
    assert CurrencyCode(" usd ").value == "USD"
    assert CurrencyCode("EUR") < CurrencyCode("GBP")

    with pytest.raises(RiskFactorPrimitiveError, match="currency_code"):
        CurrencyCode("US")


def test_tenor_normalises_uppercase_and_validates_shape() -> None:
    assert Tenor(" 5y ").value == "5Y"
    assert Tenor("10D") < Tenor("20D")

    with pytest.raises(RiskFactorPrimitiveError, match="tenor"):
        Tenor("0D")
