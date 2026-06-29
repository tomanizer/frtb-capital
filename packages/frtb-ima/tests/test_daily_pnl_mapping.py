"""Tests for the v1 daily P&L mapping spec adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from frtb_ima.adapters.daily_pnl_mapping import (
    IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS,
    MappingSpecError,
    input_hash_for_daily_pnl_vector_batch,
    load_ima_mapping_spec,
    materialize_daily_pnl_vectors_from_mapping,
    materialize_daily_pnl_vectors_from_rows,
    parse_ima_mapping_spec,
)

MAPPING_YAML = """
mapping_spec_version: 1
target_schema: ima-arrow-v1
source_system: client_risk_engine
base_currency: USD
timezone: Europe/London

sign_convention:
  pnl_positive_means: gain

tables:
  daily_pnl_vectors:
    source: daily_pnl.csv
    target: ima_daily_pnl_vectors
    fields:
      desk_id: DESK
      business_date: COB_DATE
      apl: ACTUAL_PNL
      hpl: HYPOTHETICAL_PNL
      rtpl: RISK_THEORETICAL_PNL
      var_975: VAR_975
      var_99: VAR_99
      source_row_id: ROW_ID

risk_factor_aliases:
  IR_USD_SWAP_10Y: rates.usd.swap.10y
"""


def test_daily_pnl_mapping_materializes_sorted_readonly_vectors() -> None:
    spec = parse_ima_mapping_spec(MAPPING_YAML)
    rows = [
        {
            "ROW_ID": "r2",
            "DESK": "Rates",
            "COB_DATE": "2025-01-03",
            "ACTUAL_PNL": "2.5",
            "HYPOTHETICAL_PNL": "2.0",
            "RISK_THEORETICAL_PNL": "1.5",
            "VAR_975": "10.0",
            "VAR_99": "12.0",
        },
        {
            "ROW_ID": "r1",
            "DESK": "Rates",
            "COB_DATE": "2025-01-02",
            "ACTUAL_PNL": "1.5",
            "HYPOTHETICAL_PNL": "1.0",
            "RISK_THEORETICAL_PNL": "0.5",
            "VAR_975": "9.0",
            "VAR_99": "11.0",
        },
    ]

    result = materialize_daily_pnl_vectors_from_rows(rows, spec)
    batch = result.batch

    assert spec.risk_factor_aliases["IR_USD_SWAP_10Y"] == "rates.usd.swap.10y"
    assert batch.observation_count == 2
    assert batch.business_dates.astype("datetime64[D]").astype(str).tolist() == [
        "2025-01-02",
        "2025-01-03",
    ]
    assert batch.apl.tolist() == [1.5, 2.5]
    assert batch.hpl.tolist() == [1.0, 2.0]
    assert batch.rtpl.tolist() == [0.5, 1.5]
    assert batch.var_99.tolist() == [11.0, 12.0]
    assert batch.input_hash == input_hash_for_daily_pnl_vector_batch(batch)
    assert not batch.apl.flags.writeable
    assert not batch.business_dates.flags.writeable
    assert result.report.as_dict()["row_count_mapped"] == 2
    assert result.report.passed


def test_daily_pnl_mapping_inverts_positive_loss_source_pnl() -> None:
    spec = parse_ima_mapping_spec(
        MAPPING_YAML.replace("pnl_positive_means: gain", "pnl_positive_means: loss")
    )

    result = materialize_daily_pnl_vectors_from_rows(
        [
            {
                "ROW_ID": "r1",
                "DESK": "Rates",
                "COB_DATE": "2025-01-02",
                "ACTUAL_PNL": "3.0",
                "HYPOTHETICAL_PNL": "2.0",
                "RISK_THEORETICAL_PNL": "1.0",
                "VAR_975": "9.0",
                "VAR_99": "11.0",
            }
        ],
        spec,
    )

    assert result.batch.apl.tolist() == [-3.0]
    assert result.batch.hpl.tolist() == [-2.0]
    assert result.batch.rtpl.tolist() == [-1.0]
    assert result.batch.var_99.tolist() == [11.0]


def test_daily_pnl_mapping_rejects_invalid_rows_and_reports_duplicates() -> None:
    spec = parse_ima_mapping_spec(MAPPING_YAML)

    result = materialize_daily_pnl_vectors_from_rows(
        [
            {
                "ROW_ID": "good",
                "DESK": "Rates",
                "COB_DATE": "2025-01-02",
                "ACTUAL_PNL": "1.0",
                "HYPOTHETICAL_PNL": "1.0",
                "RISK_THEORETICAL_PNL": "1.0",
                "VAR_975": "9.0",
                "VAR_99": "11.0",
            },
            {
                "ROW_ID": "bad-date",
                "DESK": "Rates",
                "COB_DATE": "2025/01/03",
                "ACTUAL_PNL": "1.0",
                "HYPOTHETICAL_PNL": "1.0",
                "RISK_THEORETICAL_PNL": "1.0",
                "VAR_975": "9.0",
                "VAR_99": "11.0",
            },
            {
                "ROW_ID": "duplicate",
                "DESK": "Rates",
                "COB_DATE": "2025-01-02",
                "ACTUAL_PNL": "2.0",
                "HYPOTHETICAL_PNL": "2.0",
                "RISK_THEORETICAL_PNL": "2.0",
                "VAR_975": "9.0",
                "VAR_99": "11.0",
            },
        ],
        spec,
    )

    report = result.report.as_dict()

    assert report["row_count_read"] == 3
    assert report["row_count_mapped"] == 1
    assert report["row_count_rejected"] == 2
    assert not result.report.passed
    assert [finding.code for finding in result.report.findings] == [
        "DAILY_PNL_ROW_REJECTED",
        "DAILY_PNL_DUPLICATE_DESK_DATE",
    ]


def test_daily_pnl_mapping_requires_explicit_sign_convention() -> None:
    with pytest.raises(MappingSpecError, match="sign_convention"):
        parse_ima_mapping_spec(MAPPING_YAML.replace("pnl_positive_means: gain", ""))


def test_daily_pnl_mapping_rejects_unknown_target_fields() -> None:
    with pytest.raises(MappingSpecError, match="unknown daily_pnl_vectors target fields"):
        parse_ima_mapping_spec(MAPPING_YAML.replace("source_row_id: ROW_ID", "mystery: X"))


def test_daily_pnl_mapping_exposes_daily_pnl_column_specs() -> None:
    assert [spec.name for spec in IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS] == [
        "desk_id",
        "business_date",
        "apl",
        "hpl",
        "rtpl",
        "var_975",
        "var_99",
        "source_row_id",
    ]
    batch = materialize_daily_pnl_vectors_from_rows(
        [
            {
                "ROW_ID": "r1",
                "DESK": "Rates",
                "COB_DATE": "2025-01-02",
                "ACTUAL_PNL": "1.0",
                "HYPOTHETICAL_PNL": "1.0",
                "RISK_THEORETICAL_PNL": "1.0",
                "VAR_975": "",
                "VAR_99": "",
            }
        ],
        parse_ima_mapping_spec(MAPPING_YAML),
    ).batch
    assert batch.var_99.tolist() == [0.0]
    assert batch.var_99_present.tolist() == [False]


def test_daily_pnl_mapping_fixture_materializes_from_mapping_yaml() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "daily_pnl_mapping_v1"
    spec = load_ima_mapping_spec(fixture_root / "mapping.yaml")
    expected_report = json.loads(
        (fixture_root / "expected_validation_report.json").read_text(encoding="utf-8")
    )

    result = materialize_daily_pnl_vectors_from_mapping(spec, source_root=fixture_root)

    assert result.batch.observation_count == 3
    assert result.batch.desk_ids.tolist() == ["Credit", "Rates", "Rates"]
    assert result.batch.business_dates.astype("datetime64[D]").astype(str).tolist() == [
        "2025-01-02",
        "2025-01-02",
        "2025-01-03",
    ]
    assert result.batch.apl.tolist() == [-1.25, 1.5, -2.0]
    assert result.batch.hpl.tolist() == [-1.1, 1.25, -1.75]
    assert result.batch.rtpl.tolist() == [-0.95, 1.0, -1.5]
    assert result.batch.var_975.tolist() == [7.5, 9.5, 10.5]
    assert result.batch.var_99_present.tolist() == [True, True, True]
    assert result.report.row_count_read == 4
    assert result.report.row_count_mapped == 3
    assert result.report.row_count_rejected == 1
    assert [finding.code for finding in result.report.findings] == [
        "DAILY_PNL_DUPLICATE_DESK_DATE"
    ]
    assert {
        "target_schema": result.report.target_schema,
        "source_system": result.report.source_system,
        "source_file": result.report.source_file,
        "row_count_read": result.report.row_count_read,
        "row_count_mapped": result.report.row_count_mapped,
        "row_count_rejected": result.report.row_count_rejected,
        "finding_codes": [finding.code for finding in result.report.findings],
    } == expected_report
