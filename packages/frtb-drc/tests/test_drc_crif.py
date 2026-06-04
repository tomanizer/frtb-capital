from __future__ import annotations

from pathlib import Path

from frtb_drc import (
    DefaultDirection,
    DrcCrifDirectionStrategy,
    DrcRiskClass,
    adapt_drc_crif_rows,
    build_drc_ctp_batch_from_arrow,
    build_drc_nonsec_batch_from_arrow,
    build_drc_securitisation_non_ctp_batch_from_arrow,
)


def test_drc_crif_adapter_accepts_nonsec_row_with_lineage_and_arrow_handoff() -> None:
    result = adapt_drc_crif_rows(
        [
            {
                "TradeID": "corp-alpha-long",
                "RowID": "vendor-row-1",
                "Desk": "credit-desk",
                "Entity": "bank-na",
                "RiskType": "DRC_NONSEC",
                "Product": "Bond",
                "Direction": "Buy",
                "Qualifier": "issuer-alpha",
                "Bucket": "Corporate",
                "Seniority": "Senior",
                "Rating": "IG",
                "Notional": "100.0",
                "MarketValue": "98.0",
                "Maturity": "1.5",
                "Currency": "USD",
                "RegulatoryCitations": "US_NPR_210_B_1_IV;US_NPR_210_B_3_II",
            }
        ],
        source_system="vendor-x",
        source_file="drc.csv",
    )

    assert result.accepted_count == 1
    assert result.rejected_count == 0
    position = result.positions[0]
    assert position.position_id == "corp-alpha-long"
    assert position.default_direction is DefaultDirection.LONG
    assert position.issuer_id == "issuer-alpha"
    assert position.bucket_key == "CORPORATE"
    assert position.lineage is not None
    assert position.lineage.source_system == "vendor-x"
    assert position.lineage.source_column_map["issuer_id"] == "Qualifier"
    assert position.citation_ids == ("US_NPR_210_B_1_IV", "US_NPR_210_B_3_II")

    handoffs = result.to_arrow_tables()
    handoff = handoffs[DrcRiskClass.NON_SECURITISATION]
    batch = build_drc_nonsec_batch_from_arrow(handoff)
    assert handoff.accepted.num_rows == 1
    assert handoff.rejected is not None
    assert handoff.rejected.num_rows == 0
    assert batch.row_count == 1
    assert batch.position_ids[0] == "corp-alpha-long"
    assert batch.source_hash == result.source_hash


def test_drc_crif_adapter_maps_signed_notional_direction_to_magnitude() -> None:
    result = adapt_drc_crif_rows(
        [
            {
                "position_id": "corp-alpha-short",
                "source_row_id": "vendor-row-2",
                "desk_id": "credit-desk",
                "legal_entity": "bank-na",
                "risk_class": "NON_SECURITISATION",
                "instrument_type": "BOND",
                "issuer_id": "issuer-alpha",
                "bucket_key": "CORPORATE",
                "seniority": "SENIOR_DEBT",
                "credit_quality": "INVESTMENT_GRADE",
                "notional": -40.0,
                "market_value": -39.0,
                "maturity_years": 1.0,
                "currency": "USD",
                "citation_ids": ("US_NPR_210_B_1_IV", "US_NPR_210_B_3_II"),
            }
        ],
        direction_strategy=DrcCrifDirectionStrategy.SIGNED_NOTIONAL,
    )

    assert result.rejected_rows == ()
    assert result.positions[0].default_direction is DefaultDirection.SHORT
    assert result.positions[0].notional == 40.0
    assert result.positions[0].market_value == 39.0
    assert result.positions[0].citation_ids == ("US_NPR_210_B_1_IV", "US_NPR_210_B_3_II")


def test_drc_crif_adapter_returns_deterministic_rejections() -> None:
    result = adapt_drc_crif_rows(
        [
            {
                "RowID": "missing-position",
                "RiskType": "DRC_NONSEC",
                "Direction": "LONG",
                "Notional": "10",
                "Maturity": "1",
                "Currency": "USD",
            },
            {
                "TradeID": "unsupported-risk",
                "RowID": "unsupported-risk-row",
                "RiskType": "DRC_UNKNOWN",
                "Direction": "LONG",
                "Notional": "10",
                "Maturity": "1",
                "Currency": "USD",
            },
            {
                "TradeID": "ambiguous-direction",
                "RowID": "ambiguous-direction-row",
                "RiskType": "DRC_NONSEC",
                "Direction": "hedged",
                "Notional": "10",
                "Maturity": "1",
                "Currency": "USD",
            },
            {
                "TradeID": "zero-signed",
                "RowID": "zero-signed-row",
                "RiskType": "DRC_NONSEC",
                "Notional": "0",
                "Maturity": "1",
                "Currency": "USD",
            },
        ],
    )

    assert result.positions == ()
    assert [row.source_row_id for row in result.rejected_rows] == [
        "missing-position",
        "unsupported-risk-row",
        "ambiguous-direction-row",
        "zero-signed-row",
    ]
    assert [row.reason_code for row in result.rejected_rows] == [
        "drc_crif.missing_required_field",
        "drc_crif.unsupported_risk_class",
        "drc_crif.ambiguous_direction",
        "drc_crif.ambiguous_direction",
    ]
    assert [diagnostic.row_id for diagnostic in result.diagnostics] == [
        "missing-position",
        "unsupported-risk-row",
        "ambiguous-direction-row",
        "zero-signed-row",
    ]


def test_drc_crif_adapter_rejects_ambiguous_source_columns_without_raising() -> None:
    result = adapt_drc_crif_rows(
        [
            {
                "TradeID": "ambiguous-row-id",
                "RowID": "vendor-row-a",
                "source_row_id": "vendor-row-b",
                "Desk": "credit-desk",
                "Entity": "bank-na",
                "RiskType": "DRC_NONSEC",
                "Product": "Bond",
                "Direction": "LONG",
                "Qualifier": "issuer-alpha",
                "Bucket": "Corporate",
                "Seniority": "Senior",
                "Rating": "IG",
                "Notional": "100.0",
                "Maturity": "1.5",
                "Currency": "USD",
                "RegulatoryCitations": "US_NPR_210_B_1_IV",
            },
            {
                "TradeID": "ambiguous-direction-source",
                "RowID": "vendor-row-ambiguous-direction",
                "Desk": "credit-desk",
                "Entity": "bank-na",
                "RiskType": "DRC_NONSEC",
                "Product": "Bond",
                "Direction": "LONG",
                "LongShort": "SHORT",
                "Qualifier": "issuer-alpha",
                "Bucket": "Corporate",
                "Seniority": "Senior",
                "Rating": "IG",
                "Notional": "100.0",
                "Maturity": "1.5",
                "Currency": "USD",
                "RegulatoryCitations": "US_NPR_210_B_1_IV",
            },
        ],
    )

    assert result.positions == ()
    assert [row.source_row_id for row in result.rejected_rows] == [
        "row-1",
        "vendor-row-ambiguous-direction",
    ]
    assert [row.reason_code for row in result.rejected_rows] == [
        "drc_crif.ambiguous_source_column",
        "drc_crif.ambiguous_source_column",
    ]
    assert set(result.rejected_rows[0].source_columns) == {"RowID", "source_row_id"}
    assert set(result.rejected_rows[1].source_columns) == {"Direction", "LongShort"}
    assert result.rejected_rows[0].source_values["source_row_id"] == {
        "RowID": "vendor-row-a",
        "source_row_id": "vendor-row-b",
    }


def test_drc_crif_adapter_builds_class_specific_sec_and_ctp_handoffs() -> None:
    result = adapt_drc_crif_rows(
        [
            {
                "position_id": "sec-alpha",
                "source_row_id": "sec-row",
                "desk_id": "credit-desk",
                "legal_entity": "bank-na",
                "risk_class": "SEC_NON_CTP",
                "instrument_type": "SECURITIZATION_TRANCHE",
                "default_direction": "LONG",
                "tranche_id": "tranche-alpha",
                "bucket_key": "SEC_CORPORATE",
                "notional": 100.0,
                "market_value": 21.0,
                "maturity_years": 1.0,
                "currency": "USD",
                "citation_ids": "US_NPR_210_C_2",
            },
            {
                "position_id": "ctp-alpha",
                "source_row_id": "ctp-row",
                "desk_id": "credit-desk",
                "legal_entity": "bank-na",
                "risk_class": "CTP",
                "instrument_type": "INDEX_TRANCHE",
                "default_direction": "SHORT",
                "index_series_id": "cdx-ig-42",
                "bucket_key": "CTP",
                "notional": 100.0,
                "market_value": 12.0,
                "maturity_years": 1.0,
                "currency": "USD",
                "citation_ids": "US_NPR_210_D_2",
            },
        ]
    )

    handoffs = result.to_arrow_tables()
    sec_batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        handoffs[DrcRiskClass.SECURITISATION_NON_CTP]
    )
    ctp_batch = build_drc_ctp_batch_from_arrow(handoffs[DrcRiskClass.CORRELATION_TRADING_PORTFOLIO])
    assert sec_batch.row_count == 1
    assert ctp_batch.row_count == 1
    assert sec_batch.position_ids[0] == "sec-alpha"
    assert ctp_batch.position_ids[0] == "ctp-alpha"


def test_drc_crif_adapter_keeps_boundary_free_of_sibling_and_dataframe_imports() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/frtb_drc/crif.py").read_text()

    assert "frtb_sbm" not in source
    assert "frtb_ima" not in source
    assert "frtb_rrao" not in source
    assert "frtb_cva" not in source
    assert "import pandas" not in source
    assert "import polars" not in source
