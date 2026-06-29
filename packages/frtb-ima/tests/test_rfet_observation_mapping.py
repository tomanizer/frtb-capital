"""Tests for RFET observation mapping into the existing Arrow target."""

from __future__ import annotations

import json
from pathlib import Path

from frtb_ima.adapters.daily_pnl_mapping import load_ima_mapping_spec
from frtb_ima.adapters.rfet_observation_mapping import materialize_rfet_observations_from_mapping


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
