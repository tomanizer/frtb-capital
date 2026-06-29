"""Tests for RFET observation mapping into the existing Arrow target."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from frtb_ima.adapters.mapping_spec import (
    MappingSpecError,
    load_ima_mapping_spec,
    parse_ima_mapping_spec,
)
from frtb_ima.adapters.rfet_observation_mapping import (
    materialize_rfet_observations_from_mapping,
    materialize_rfet_observations_from_rows,
)

RFET_MAPPING_YAML = """
mapping_spec_version: 1
target_schema: ima-arrow-v1
source_system: client_risk_engine
base_currency: USD
timezone: Europe/London

sign_convention:
  pnl_positive_means: gain

tables:
  rfet_observations:
    source: rfet_observations.csv
    target: ima_rfet_observations
    fields:
      risk_factor_name: RF_NAME
      observation_date: OBS_DATE
      source: OBS_SOURCE
      verifiable: VERIFIABLE
      source_row_id: SOURCE_ROW
"""


def test_rfet_observation_mapping_fixture_materializes_existing_arrow_batch() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "rfet_observation_mapping_v1"
    spec = load_ima_mapping_spec(fixture_root / "mapping.yaml")
    expected_report = json.loads(
        (fixture_root / "expected_validation_report.json").read_text(encoding="utf-8")
    )

    result = materialize_rfet_observations_from_mapping(spec, source_root=fixture_root)

    assert result.batch.observation_count == 3
    assert result.batch.risk_factor_names.tolist() == [
        "EUR_SWAP_10Y",
        "USD_SWAP_5Y",
        "USD_SWAP_5Y",
    ]
    assert result.batch.observation_dates.astype("datetime64[D]").astype(str).tolist() == [
        "2025-01-03",
        "2025-01-02",
        "2025-01-03",
    ]
    assert result.batch.sources.tolist() == ["trade", "trade", "quote"]
    assert result.batch.vendor_ids.tolist() == ["VENDOR_B", "VENDOR_A", "VENDOR_A"]
    assert result.batch.verifiable.tolist() == [False, True, True]
    assert result.batch.source_row_ids.tolist() == ["rfet-003", "rfet-001", "rfet-002"]
    assert {
        "target_schema": result.report.target_schema,
        "source_system": result.report.source_system,
        "source_file": result.report.source_file,
        "row_count_read": result.report.row_count_read,
        "row_count_mapped": result.report.row_count_mapped,
        "row_count_rejected": result.report.row_count_rejected,
        "finding_codes": [finding.code for finding in result.report.findings],
    } == expected_report


def test_rfet_observation_mapping_accepts_rfet_only_spec() -> None:
    spec = parse_ima_mapping_spec(RFET_MAPPING_YAML)

    assert spec.daily_pnl_vectors is None
    assert spec.rfet_observations is not None


def test_rfet_observation_mapping_reports_bad_rows_and_boolean_edges() -> None:
    spec = parse_ima_mapping_spec(RFET_MAPPING_YAML)

    result = materialize_rfet_observations_from_rows(
        [
            {
                "SOURCE_ROW": "yes-row",
                "RF_NAME": "USD_SWAP_5Y",
                "OBS_DATE": "2025-01-02",
                "OBS_SOURCE": "trade",
                "VERIFIABLE": "yes",
            },
            {
                "SOURCE_ROW": "false-row",
                "RF_NAME": "EUR_SWAP_10Y",
                "OBS_DATE": "2025-01-03",
                "OBS_SOURCE": "quote",
                "VERIFIABLE": "f",
            },
            {
                "SOURCE_ROW": "bad-date",
                "RF_NAME": "USD_SWAP_10Y",
                "OBS_DATE": "2025/01/04",
                "OBS_SOURCE": "trade",
                "VERIFIABLE": "true",
            },
            {
                "SOURCE_ROW": "bad-bool",
                "RF_NAME": "GBP_SWAP_2Y",
                "OBS_DATE": "2025-01-05",
                "OBS_SOURCE": "trade",
                "VERIFIABLE": "maybe",
            },
        ],
        spec,
    )

    assert result.batch.observation_count == 2
    assert result.batch.verifiable.tolist() == [False, True]
    assert result.report.row_count_rejected == 2
    assert [finding.row_id for finding in result.report.findings] == ["bad-date", "bad-bool"]
    assert [finding.code for finding in result.report.findings] == [
        "RFET_OBSERVATION_ROW_REJECTED",
        "RFET_OBSERVATION_ROW_REJECTED",
    ]
    assert not result.report.passed


def test_rfet_observation_mapping_requires_rfet_table_for_materialization() -> None:
    spec = parse_ima_mapping_spec(
        """
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
      apl: APL
      hpl: HPL
      rtpl: RTPL
"""
    )

    with pytest.raises(MappingSpecError, match="tables.rfet_observations"):
        materialize_rfet_observations_from_rows([], spec)


def test_rfet_observation_mapping_rejects_all_bad_rows() -> None:
    spec = parse_ima_mapping_spec(RFET_MAPPING_YAML)

    with pytest.raises(ValueError, match="no accepted rows"):
        materialize_rfet_observations_from_rows(
            [
                {
                    "SOURCE_ROW": "bad-date",
                    "RF_NAME": "USD_SWAP_10Y",
                    "OBS_DATE": "2025/01/04",
                    "OBS_SOURCE": "trade",
                    "VERIFIABLE": "true",
                }
            ],
            spec,
        )
