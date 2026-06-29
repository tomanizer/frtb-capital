"""Tests for aggregate v1 IMA mapping validation reports."""

from __future__ import annotations

import json

import pytest

from frtb_ima.adapters import build_ima_mapping_validation_report
from frtb_ima.adapters.daily_pnl_mapping import DailyPnlValidationReport, MappingFinding
from frtb_ima.adapters.scenario_pnl_mapping import ScenarioPnlValidationReport


def test_build_ima_mapping_validation_report_aggregates_table_reports() -> None:
    daily_report = DailyPnlValidationReport(
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
        source_file="daily.csv",
        mapping_hash="mapping-hash",
        source_hash="daily-source-hash",
        row_count_read=3,
        row_count_mapped=2,
        row_count_rejected=1,
        findings=(
            MappingFinding(
                severity="ERROR",
                code="DAILY_PNL_ROW_REJECTED",
                message="bad row",
                row_id="daily-2",
            ),
        ),
    )
    scenario_report = ScenarioPnlValidationReport(
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
        source_file="scenario.csv",
        mapping_hash="mapping-hash",
        source_hash="scenario-source-hash",
        row_count_read=8,
        row_count_mapped=8,
        row_count_rejected=0,
    )

    report = build_ima_mapping_validation_report(
        {
            "ima_scenario_pnl_vectors": scenario_report,
            "ima_daily_pnl_vectors": daily_report,
        }
    )
    payload = report.as_dict()

    assert not report.passed
    assert payload["report_schema"] == "ima-mapping-validation-report-v1"
    assert payload["target_schema"] == "ima-arrow-v1"
    assert payload["source_system"] == "client_risk_engine"
    assert payload["mapping_hash"] == "mapping-hash"
    assert len(str(payload["report_hash"])) == 64
    assert payload["row_count_read"] == 11
    assert payload["row_count_mapped"] == 10
    assert payload["row_count_rejected"] == 1
    assert payload["finding_count"] == 1
    assert payload["source_hashes"] == {
        "ima_daily_pnl_vectors": "daily-source-hash",
        "ima_scenario_pnl_vectors": "scenario-source-hash",
    }
    assert [table["table_name"] for table in payload["tables"]] == [
        "ima_daily_pnl_vectors",
        "ima_scenario_pnl_vectors",
    ]
    assert payload["tables"][0]["findings"] == [
        {
            "table_name": "ima_daily_pnl_vectors",
            "severity": "ERROR",
            "code": "DAILY_PNL_ROW_REJECTED",
            "message": "bad row",
            "row_id": "daily-2",
        }
    ]
    assert json.loads(report.to_json()) == payload


def test_build_ima_mapping_validation_report_passes_when_all_tables_pass() -> None:
    daily_report = DailyPnlValidationReport(
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
        source_file="daily.csv",
        mapping_hash="mapping-hash",
        source_hash="daily-source-hash",
        row_count_read=1,
        row_count_mapped=1,
        row_count_rejected=0,
    )

    report = build_ima_mapping_validation_report({"ima_daily_pnl_vectors": daily_report})

    assert report.passed
    assert report.finding_count == 0
    assert report.row_count_read == 1


def test_build_ima_mapping_validation_report_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one table report"):
        build_ima_mapping_validation_report({})


def test_build_ima_mapping_validation_report_requires_consistent_mapping_hash() -> None:
    first = DailyPnlValidationReport(
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
        source_file="daily.csv",
        mapping_hash="mapping-hash-1",
        source_hash="daily-source-hash",
        row_count_read=1,
        row_count_mapped=1,
        row_count_rejected=0,
    )
    second = ScenarioPnlValidationReport(
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
        source_file="scenario.csv",
        mapping_hash="mapping-hash-2",
        source_hash="scenario-source-hash",
        row_count_read=1,
        row_count_mapped=1,
        row_count_rejected=0,
    )

    with pytest.raises(ValueError, match="mapping_hash"):
        build_ima_mapping_validation_report(
            {
                "ima_daily_pnl_vectors": first,
                "ima_scenario_pnl_vectors": second,
            }
        )
