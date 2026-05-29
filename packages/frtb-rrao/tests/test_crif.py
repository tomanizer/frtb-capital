from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoRegulatoryProfile,
    adapt_crif_records,
    adapt_fnet_records,
    adapt_rrao_records,
    calculate_rrao_capital,
    crif,
)


def test_crif_adapter_maps_supported_risk_types_to_canonical_positions() -> None:
    result = adapt_crif_records(
        (
            {
                "TradeId": "crif-exotic-001",
                "RowID": "row-001",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "AmountUSD": "1000000",
                "Currency": "USD",
                "RiskType": "RRAO_1_PERCENT",
                "ProductType": "weather derivative",
            },
            {
                "TradeId": "crif-gap-001",
                "RowID": "row-002",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "AmountUSD": "2000000",
                "Currency": "USD",
                "RiskType": "RRAO_01_PERCENT",
                "EvidenceType": "GAP_RISK",
                "ProductType": "gap risk payoff",
            },
        ),
        source_file="crif.csv",
    )

    assert result.rejected_rows == ()
    assert result.warnings == ()
    assert [position.position_id for position in result.positions] == [
        "crif-exotic-001",
        "crif-gap-001",
    ]
    assert result.positions[0].classification_hint is RraoClassification.EXOTIC
    assert result.positions[0].evidence_type is RraoEvidenceType.EXOTIC_UNDERLYING
    assert result.positions[1].classification_hint is RraoClassification.OTHER_RESIDUAL_RISK
    assert result.positions[1].evidence_type is RraoEvidenceType.GAP_RISK
    assert result.positions[0].lineage is not None
    assert result.positions[0].lineage.source_system == "crif"
    source_column_map = result.positions[0].lineage.source_column_map
    assert ("AmountUSD", "gross_effective_notional") in source_column_map
    assert ("TradeId", "position_id") in source_column_map
    assert ("Desk", "desk_id") in source_column_map
    assert ("LegalEntity", "legal_entity") in source_column_map
    assert ("RiskType", "classification_hint") in source_column_map
    assert ("ProductType", "evidence_label") in source_column_map


def test_fnet_adapter_maps_bucket_rows_when_evidence_is_sufficient() -> None:
    result = adapt_fnet_records(
        (
            {
                "PositionID": "fnet-exotic-001",
                "RowID": "row-001",
                "DeskID": "desk-b",
                "LegalEntityID": "LE-002",
                "GrossEffectiveNotional": 1500000.0,
                "Currency": "USD",
                "Bucket": "Exotic",
                "Description": "longevity derivative",
            },
            {
                "PositionID": "fnet-behavioural-001",
                "RowID": "row-002",
                "DeskID": "desk-b",
                "LegalEntityID": "LE-002",
                "GrossEffectiveNotional": 3000000.0,
                "Currency": "USD",
                "Bucket": "Non-Exotic",
                "EvidenceType": "BEHAVIOURAL_RISK",
                "Description": "prepayment behaviour",
            },
        ),
        source_file="fnet.csv",
    )

    assert result.rejected_rows == ()
    assert [position.evidence_type for position in result.positions] == [
        RraoEvidenceType.EXOTIC_UNDERLYING,
        RraoEvidenceType.BEHAVIOURAL_RISK,
    ]


def test_crif_adapter_accepts_valid_exact_back_to_back_pair() -> None:
    result = adapt_crif_records(
        (
            {
                "TradeId": "crif-b2b-left",
                "RowID": "row-b2b-left",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "AmountUSD": "2500000",
                "Currency": "USD",
                "RiskType": "RRAO_0_PERCENT",
                "ProductType": "exact back-to-back left",
                "ExclusionReason": "EXACT_THIRD_PARTY_BACK_TO_BACK",
                "ExclusionEvidenceID": "external-match-001",
                "BackToBackMatchGroupID": "external-match-001",
                "BackToBackMatchedPositionID": "crif-b2b-right",
            },
            {
                "TradeId": "crif-b2b-right",
                "RowID": "row-b2b-right",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "AmountUSD": "2500000",
                "Currency": "USD",
                "RiskType": "RRAO_0_PERCENT",
                "ProductType": "exact back-to-back right",
                "ExclusionReason": "EXACT_THIRD_PARTY_BACK_TO_BACK",
                "ExclusionEvidenceID": "external-match-001",
                "BackToBackMatchGroupID": "external-match-001",
                "BackToBackMatchedPositionID": "crif-b2b-left",
            },
        ),
        source_file="crif.csv",
    )

    assert result.rejected_rows == ()
    assert [position.position_id for position in result.positions] == [
        "crif-b2b-left",
        "crif-b2b-right",
    ]
    assert all(
        position.exclusion_reason is RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK
        for position in result.positions
    )

    capital = calculate_rrao_capital(
        result.positions,
        context=RraoCalculationContext(
            run_id="adapter-b2b-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile=RraoRegulatoryProfile.US_NPR_2_0,
        ),
    )

    assert capital.lines == ()
    assert [line.position_id for line in capital.excluded_lines] == [
        "crif-b2b-left",
        "crif-b2b-right",
    ]
    assert capital.total_rrao == 0.0


def test_fnet_adapter_accepts_valid_exact_back_to_back_pair() -> None:
    result = adapt_fnet_records(
        (
            {
                "PositionID": "fnet-b2b-left",
                "RowID": "row-b2b-left",
                "DeskID": "desk-b",
                "LegalEntityID": "LE-002",
                "GrossEffectiveNotional": 1250000.0,
                "Currency": "USD",
                "Bucket": "Excluded",
                "Description": "exact back-to-back left",
                "ExclusionReason": "EXACT_THIRD_PARTY_BACK_TO_BACK",
                "ExclusionEvidenceID": "fnet-match-001",
                "BackToBackMatchGroupID": "fnet-match-001",
                "BackToBackMatchedPositionID": "fnet-b2b-right",
            },
            {
                "PositionID": "fnet-b2b-right",
                "RowID": "row-b2b-right",
                "DeskID": "desk-b",
                "LegalEntityID": "LE-002",
                "GrossEffectiveNotional": 1250000.0,
                "Currency": "USD",
                "Bucket": "Excluded",
                "Description": "exact back-to-back right",
                "ExclusionReason": "EXACT_THIRD_PARTY_BACK_TO_BACK",
                "ExclusionEvidenceID": "fnet-match-001",
                "BackToBackMatchGroupID": "fnet-match-001",
                "BackToBackMatchedPositionID": "fnet-b2b-left",
            },
        ),
        source_file="fnet.csv",
    )

    assert result.rejected_rows == ()
    assert [position.position_id for position in result.positions] == [
        "fnet-b2b-left",
        "fnet-b2b-right",
    ]


def test_adapter_rejects_ambiguous_classification_and_notional_conventions() -> None:
    result = adapt_rrao_records(
        (
            {
                "PositionID": "generic-non-exotic",
                "RowID": "row-001",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "Amount": 1000000.0,
                "Currency": "USD",
                "RiskType": "RRAO_01_PERCENT",
            },
            {
                "PositionID": "ambiguous-weighted-notional",
                "RowID": "row-002",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "WeightedNotional": 1000000.0,
                "Currency": "USD",
                "Bucket": "Exotic",
            },
        )
    )

    assert result.positions == ()
    assert [row.field for row in result.rejected_rows] == ["EvidenceType", "WeightedNotional"]
    assert (
        "generic non-exotic RRAO rows require specific evidence type"
        in result.rejected_rows[0].reason
    )
    assert (
        "WeightedNotional requires explicit gross notional convention"
        in result.rejected_rows[1].reason
    )


def test_adapter_rejects_non_iterable_or_mapping_record_batches() -> None:
    with pytest.raises(RraoInputError, match="records must be an iterable of mapping rows"):
        adapt_rrao_records({"PositionID": "not-a-batch"})
    with pytest.raises(RraoInputError, match="records must be an iterable of mapping rows"):
        adapt_rrao_records(object())


def test_adapter_rejects_non_mapping_rows_without_stopping_batch() -> None:
    result = adapt_rrao_records(
        (
            "not-a-row",
            {
                "PositionID": "valid-exotic",
                "RowID": "row-002",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "Amount": 1000000.0,
                "Currency": "USD",
                "Bucket": "Exotic",
            },
        )
    )

    assert [position.position_id for position in result.positions] == ["valid-exotic"]
    assert result.rejected_rows[0].source_row_id == "row-000001"
    assert result.rejected_rows[0].field == "record"


@pytest.mark.parametrize(
    ("row_updates", "expected_field", "expected_reason"),
    (
        ({"Desk": ""}, "desk_id", "desk_id field is required"),
        ({"Bucket": ""}, "RiskType/Bucket", "row must include CRIF RiskType or FNet Bucket"),
        (
            {"Bucket": "Unsupported"},
            "RiskType/Bucket",
            "unsupported RRAO adapter classification label",
        ),
        (
            {"Bucket": "Non-Exotic", "EvidenceType": "UNKNOWN"},
            "EvidenceType",
            "unsupported adapter evidence type",
        ),
        ({"Amount": None}, "Amount", "gross effective notional must be numeric"),
        ({"Amount": True}, "Amount", "gross effective notional must be numeric"),
        ({"Amount": "not-numeric"}, "Amount", "gross effective notional must be numeric"),
        (
            {
                "Bucket": "Excluded",
                "ExclusionReason": "UNKNOWN",
                "ExclusionEvidenceID": "evidence-001",
            },
            "ExclusionReason",
            "unsupported adapter exclusion reason",
        ),
        (
            {"BackToBackMatchGroupID": "match-001"},
            "back_to_back_match",
            "require both match group and matched position id",
        ),
    ),
)
def test_adapter_reports_row_level_rejections(
    row_updates: dict[str, object],
    expected_field: str,
    expected_reason: str,
) -> None:
    row = _base_adapter_row()
    row.update(row_updates)

    result = adapt_rrao_records((row,))

    assert result.positions == ()
    assert result.rejected_rows[0].field == expected_field
    assert expected_reason in result.rejected_rows[0].reason
    assert ("PositionID", "'invalid-row'") in result.rejected_rows[0].source_row


def test_adapter_reports_missing_notional_as_row_rejection() -> None:
    row = _base_adapter_row()
    del row["Amount"]

    result = adapt_rrao_records((row,))

    assert result.positions == ()
    assert result.rejected_rows[0].field == "gross_effective_notional"
    assert "gross effective notional field is required" in result.rejected_rows[0].reason


def test_adapter_reports_batch_validation_rejections() -> None:
    row = _base_adapter_row()
    row.update(
        {
            "Bucket": "Excluded",
            "ExclusionReason": "EXACT_THIRD_PARTY_BACK_TO_BACK",
            "ExclusionEvidenceID": "external-match-001",
            "BackToBackMatchGroupID": "external-match-001",
            "BackToBackMatchedPositionID": "missing-partner",
        }
    )

    result = adapt_rrao_records((row,))

    assert result.positions == ()
    assert result.rejected_rows[0].source_row_id == "row-invalid"
    assert result.rejected_rows[0].field is not None


def test_adapter_records_warnings_and_can_feed_public_calculation() -> None:
    adapter_result = adapt_rrao_records(
        (
            {
                "PositionID": "fallback-row-id",
                "Desk": "desk-a",
                "LegalEntity": "LE-001",
                "WeightedNotional": "-1000000",
                "NotionalConvention": "gross_effective_notional",
                "Currency": "USD",
                "Bucket": "Exotic",
            },
        ),
        source_sign_convention="signed_absolute",
    )

    assert adapter_result.rejected_rows == ()
    assert [warning.field for warning in adapter_result.warnings] == [
        "source_row_id",
        "WeightedNotional",
    ]
    assert adapter_result.positions[0].source_row_id == "row-000001"
    assert adapter_result.positions[0].gross_effective_notional == 1000000.0

    capital = calculate_rrao_capital(
        adapter_result.positions,
        context=RraoCalculationContext(
            run_id="adapter-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile=RraoRegulatoryProfile.US_NPR_2_0,
        ),
    )

    assert capital.total_rrao == 10000.0


def test_adapter_does_not_import_pandas() -> None:
    assert "pandas" not in Path(crif.__file__).read_text(encoding="utf-8")


def _base_adapter_row() -> dict[str, object]:
    return {
        "PositionID": "invalid-row",
        "RowID": "row-invalid",
        "Desk": "desk-a",
        "LegalEntity": "LE-001",
        "Amount": 1000000.0,
        "Currency": "USD",
        "Bucket": "Exotic",
    }
