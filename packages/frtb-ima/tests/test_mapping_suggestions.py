"""Tests for v1 IMA mapping suggestion reports."""

from __future__ import annotations

import json

import pytest

from frtb_ima.adapters import (
    build_ima_mapping_suggestion_report,
    profile_source_rows,
)


def test_build_mapping_suggestion_report_ranks_daily_pnl_candidates() -> None:
    profile = profile_source_rows(
        [
            {
                "DESK": "Rates",
                "COB_DATE": "2025-01-02",
                "ACTUAL_PNL": "10.5",
                "HYPOTHETICAL_PNL": "9.5",
                "RISK_THEORETICAL_PNL": "9.0",
                "SOURCE_ROW": "row-1",
            },
            {
                "DESK": "Rates",
                "COB_DATE": "2025-01-03",
                "ACTUAL_PNL": "11.5",
                "HYPOTHETICAL_PNL": "10.5",
                "RISK_THEORETICAL_PNL": "10.0",
                "SOURCE_ROW": "row-2",
            },
        ],
        source_name="daily.csv",
    )

    report = build_ima_mapping_suggestion_report(
        {"ima_daily_pnl_vectors": profile},
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
    )
    payload = report.as_dict()
    fields = {field["target_field"]: field for field in payload["tables"][0]["fields"]}

    assert payload["report_schema"] == "ima-mapping-suggestion-report-v1"
    assert payload["human_review_required"] is True
    assert len(str(payload["report_hash"])) == 64
    assert payload["source_hashes"] == {"ima_daily_pnl_vectors": profile.source_hash}
    assert payload["tables"][0]["table_name"] == "ima_daily_pnl_vectors"
    assert payload["tables"][0]["missing_required_fields"] == []
    assert fields["desk_id"]["candidates"][0]["source_column"] == "DESK"
    assert fields["business_date"]["candidates"][0]["source_column"] == "COB_DATE"
    assert fields["apl"]["candidates"][0]["source_column"] == "ACTUAL_PNL"
    assert fields["hpl"]["candidates"][0]["source_column"] == "HYPOTHETICAL_PNL"
    assert fields["rtpl"]["candidates"][0]["source_column"] == "RISK_THEORETICAL_PNL"
    assert fields["var_975"]["status"] == "needs_mapping"
    assert json.loads(report.to_json()) == payload


def test_build_mapping_suggestion_report_records_missing_required_fields() -> None:
    profile = profile_source_rows(
        [{"SCENARIO_ID": "s1", "SCENARIO_DATE": "2025-01-02", "PNL": "1.0"}],
        source_name="scenario.csv",
    )

    report = build_ima_mapping_suggestion_report(
        {"ima_scenario_pnl_vectors": profile},
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
    )
    table = report.as_dict()["tables"][0]

    assert table["missing_required_fields"] == ["position_id", "risk_factor_name"]
    assert report.missing_required_field_count == 2


def test_build_mapping_suggestion_report_can_score_default_profile_for_all_targets() -> None:
    profile = profile_source_rows(
        [
            {
                "RISK_FACTOR": "USD.IR.1Y",
                "RISK_CLASS": "GIRR",
                "LH_DAYS": "20",
                "OBS_DATE": "2025-01-02",
                "EFFECTIVE_DATE": "2025-01-01",
            }
        ],
        source_name="risk-factors.csv",
    )

    report = build_ima_mapping_suggestion_report(
        {"default": profile},
        target_schema="ima-arrow-v1",
        source_system="client_risk_engine",
        targets=("ima_risk_factor_master", "ima_rfet_observations"),
    )
    payload = report.as_dict()

    assert [table["table_name"] for table in payload["tables"]] == [
        "ima_rfet_observations",
        "ima_risk_factor_master",
    ]
    rfet_fields = {field["target_field"]: field for field in payload["tables"][0]["fields"]}
    master_fields = {field["target_field"]: field for field in payload["tables"][1]["fields"]}
    assert rfet_fields["risk_factor_name"]["candidates"][0]["source_column"] == "RISK_FACTOR"
    assert rfet_fields["observation_date"]["candidates"][0]["source_column"] == "OBS_DATE"
    assert master_fields["liquidity_horizon"]["candidates"][0]["source_column"] == "LH_DAYS"
    assert master_fields["effective_date"]["candidates"][0]["source_column"] == "EFFECTIVE_DATE"


def test_build_mapping_suggestion_report_rejects_bad_inputs() -> None:
    profile = profile_source_rows([{"desk": "Rates"}])

    with pytest.raises(ValueError, match="at least one source profile"):
        build_ima_mapping_suggestion_report(
            {}, target_schema="ima-arrow-v1", source_system="client"
        )
    with pytest.raises(ValueError, match="unsupported IMA mapping targets"):
        build_ima_mapping_suggestion_report(
            {"ima_daily_pnl_vectors": profile},
            target_schema="ima-arrow-v1",
            source_system="client",
            targets=("unknown",),
        )
    with pytest.raises(ValueError, match="missing source profile"):
        build_ima_mapping_suggestion_report(
            {"ima_daily_pnl_vectors": profile},
            target_schema="ima-arrow-v1",
            source_system="client",
            targets=("ima_scenario_pnl_vectors",),
        )
    with pytest.raises(ValueError, match="max_candidates_per_field"):
        build_ima_mapping_suggestion_report(
            {"ima_daily_pnl_vectors": profile},
            target_schema="ima-arrow-v1",
            source_system="client",
            max_candidates_per_field=0,
        )
