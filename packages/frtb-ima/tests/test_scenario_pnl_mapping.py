"""Tests for scenario P&L mapping into ScenarioCube handoff objects."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from frtb_ima.adapters.mapping_spec import (
    MappingSpecError,
    load_ima_mapping_spec,
    parse_ima_mapping_spec,
)
from frtb_ima.adapters.scenario_pnl_mapping import (
    IMA_SCENARIO_PNL_VECTOR_TARGET,
    materialize_scenario_pnl_vectors_from_mapping,
    materialize_scenario_pnl_vectors_from_rows,
)
from frtb_ima.scenario import ScenarioSetType

SCENARIO_PNL_MAPPING_YAML = """
mapping_spec_version: 1
target_schema: ima-arrow-v1
source_system: client_risk_engine
base_currency: USD
timezone: Europe/London

sign_convention:
  pnl_positive_means: gain

tables:
  scenario_pnl_vectors:
    source: scenario_pnl.csv
    target: ima_scenario_pnl_vectors
    fields:
      scenario_id: SCENARIO_ID
      scenario_date: SCENARIO_DATE
      scenario_set: SCENARIO_SET
      position_id: POSITION_ID
      risk_factor_name: RISK_FACTOR
      pnl: PNL_USD
      source_row_id: SOURCE_ROW
"""


def test_scenario_pnl_mapping_fixture_materializes_scenario_cube() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "scenario_pnl_mapping_v1"
    spec = load_ima_mapping_spec(fixture_root / "mapping.yaml")
    expected_report = json.loads(
        (fixture_root / "expected_validation_report.json").read_text(encoding="utf-8")
    )

    result = materialize_scenario_pnl_vectors_from_mapping(spec, source_root=fixture_root)
    cube = result.cube

    assert cube.name == IMA_SCENARIO_PNL_VECTOR_TARGET
    assert cube.position_ids == ("POS_A", "POS_B")
    assert cube.risk_factor_names == ("EUR_SWAP_10Y", "USD_SWAP_5Y")
    assert [metadata.scenario_id for metadata in cube.scenario_metadata] == [
        "scn-001",
        "scn-002",
    ]
    assert [metadata.scenario_set for metadata in cube.scenario_metadata] == [
        ScenarioSetType.CURRENT,
        ScenarioSetType.CURRENT,
    ]
    np.testing.assert_allclose(
        cube.values,
        np.asarray(
            [
                [[-1.5, 3.0], [-0.5, 1.0]],
                [[0.25, -0.75], [-1.25, 2.0]],
            ]
        ),
    )
    assert result.batch.observation_count == 8
    assert result.batch.source_row_ids.tolist() == [
        "scenario-003",
        "scenario-001",
        "scenario-002",
        "scenario-004",
        "scenario-005",
        "scenario-006",
        "scenario-007",
        "scenario-008",
    ]
    assert not cube.values.flags.writeable
    assert not result.batch.pnl.flags.writeable
    assert result.report.row_count_read == 9
    assert result.report.row_count_mapped == 8
    assert result.report.row_count_rejected == 1
    assert [finding.code for finding in result.report.findings] == [
        "SCENARIO_PNL_DUPLICATE_KEY"
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


def test_scenario_pnl_mapping_accepts_scenario_only_spec() -> None:
    spec = parse_ima_mapping_spec(SCENARIO_PNL_MAPPING_YAML)

    assert spec.daily_pnl_vectors is None
    assert spec.rfet_observations is None
    assert spec.scenario_pnl_vectors is not None


def test_scenario_pnl_mapping_reports_bad_rows_and_metadata_conflicts() -> None:
    spec = parse_ima_mapping_spec(SCENARIO_PNL_MAPPING_YAML)

    result = materialize_scenario_pnl_vectors_from_rows(
        [
            {
                "SOURCE_ROW": "good",
                "SCENARIO_ID": "scn-001",
                "SCENARIO_DATE": "2025-01-02",
                "SCENARIO_SET": "current",
                "POSITION_ID": "POS_A",
                "RISK_FACTOR": "USD_SWAP_5Y",
                "PNL_USD": "-3.0",
            },
            {
                "SOURCE_ROW": "bad-date",
                "SCENARIO_ID": "scn-002",
                "SCENARIO_DATE": "2025/01/03",
                "SCENARIO_SET": "CURRENT",
                "POSITION_ID": "POS_A",
                "RISK_FACTOR": "USD_SWAP_5Y",
                "PNL_USD": "1.0",
            },
            {
                "SOURCE_ROW": "bad-pnl",
                "SCENARIO_ID": "scn-003",
                "SCENARIO_DATE": "2025-01-04",
                "SCENARIO_SET": "CURRENT",
                "POSITION_ID": "POS_A",
                "RISK_FACTOR": "USD_SWAP_5Y",
                "PNL_USD": "not-a-number",
            },
            {
                "SOURCE_ROW": "conflict",
                "SCENARIO_ID": "scn-001",
                "SCENARIO_DATE": "2025-01-05",
                "SCENARIO_SET": "CURRENT",
                "POSITION_ID": "POS_B",
                "RISK_FACTOR": "USD_SWAP_5Y",
                "PNL_USD": "2.0",
            },
        ],
        spec,
    )

    assert result.cube.scenario_count == 1
    assert result.report.row_count_mapped == 1
    assert result.report.row_count_rejected == 3
    assert [finding.row_id for finding in result.report.findings] == [
        "bad-date",
        "bad-pnl",
        "conflict",
    ]
    assert [finding.code for finding in result.report.findings] == [
        "SCENARIO_PNL_ROW_REJECTED",
        "SCENARIO_PNL_ROW_REJECTED",
        "SCENARIO_PNL_SCENARIO_METADATA_CONFLICT",
    ]
    assert not result.report.passed


def test_scenario_pnl_mapping_rejects_missing_cells_by_default() -> None:
    spec = parse_ima_mapping_spec(SCENARIO_PNL_MAPPING_YAML)

    with pytest.raises(ValueError, match="missing scenario/position/risk-factor cells"):
        materialize_scenario_pnl_vectors_from_rows(
            [
                {
                    "SOURCE_ROW": "row-1",
                    "SCENARIO_ID": "scn-001",
                    "SCENARIO_DATE": "2025-01-02",
                    "SCENARIO_SET": "CURRENT",
                    "POSITION_ID": "POS_A",
                    "RISK_FACTOR": "USD_SWAP_5Y",
                    "PNL_USD": "-3.0",
                },
                {
                    "SOURCE_ROW": "row-2",
                    "SCENARIO_ID": "scn-002",
                    "SCENARIO_DATE": "2025-01-03",
                    "SCENARIO_SET": "CURRENT",
                    "POSITION_ID": "POS_B",
                    "RISK_FACTOR": "USD_SWAP_5Y",
                    "PNL_USD": "-2.0",
                },
            ],
            spec,
        )


def test_scenario_pnl_mapping_allows_explicit_zero_fill_policy() -> None:
    spec = parse_ima_mapping_spec(
        SCENARIO_PNL_MAPPING_YAML.replace(
            "source_row_id: SOURCE_ROW",
            "source_row_id: SOURCE_ROW\n    missing_cells: zero",
        )
    )

    result = materialize_scenario_pnl_vectors_from_rows(
        [
            {
                "SOURCE_ROW": "row-1",
                "SCENARIO_ID": "scn-001",
                "SCENARIO_DATE": "2025-01-02",
                "SCENARIO_SET": "CURRENT",
                "POSITION_ID": "POS_A",
                "RISK_FACTOR": "USD_SWAP_5Y",
                "PNL_USD": "-3.0",
            },
            {
                "SOURCE_ROW": "row-2",
                "SCENARIO_ID": "scn-002",
                "SCENARIO_DATE": "2025-01-03",
                "SCENARIO_SET": "CURRENT",
                "POSITION_ID": "POS_B",
                "RISK_FACTOR": "USD_SWAP_5Y",
                "PNL_USD": "-2.0",
            },
        ],
        spec,
    )

    np.testing.assert_allclose(
        result.cube.values,
        np.asarray(
            [
                [[3.0], [0.0]],
                [[0.0], [2.0]],
            ]
        ),
    )
    assert result.report.passed


def test_scenario_pnl_mapping_requires_scenario_table_for_materialization() -> None:
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
  rfet_observations:
    source: rfet.csv
    target: ima_rfet_observations
    fields:
      risk_factor_name: RF_NAME
      observation_date: OBS_DATE
"""
    )

    with pytest.raises(MappingSpecError, match=r"tables\.scenario_pnl_vectors"):
        materialize_scenario_pnl_vectors_from_rows([], spec)


def test_scenario_pnl_mapping_rejects_all_bad_rows() -> None:
    spec = parse_ima_mapping_spec(SCENARIO_PNL_MAPPING_YAML)

    with pytest.raises(ValueError, match="no accepted rows"):
        materialize_scenario_pnl_vectors_from_rows(
            [
                {
                    "SOURCE_ROW": "bad-date",
                    "SCENARIO_ID": "scn-001",
                    "SCENARIO_DATE": "2025/01/02",
                    "SCENARIO_SET": "CURRENT",
                    "POSITION_ID": "POS_A",
                    "RISK_FACTOR": "USD_SWAP_5Y",
                    "PNL_USD": "1.0",
                }
            ],
            spec,
        )
