"""Tests for v1 source profiling used by IMA mapping workflows."""

from __future__ import annotations

import json

import pytest

from frtb_ima.adapters import profile_csv_source, profile_source_rows


def test_profile_source_rows_discovers_schema_and_infers_column_metadata() -> None:
    rows = [
        {
            "DESK": "Rates",
            "COB_DATE": "2025-01-03",
            "PNL": "1,200.50",
            "COUNT": "10",
            "FLAG": "yes",
        },
        {
            "DESK": "Rates",
            "COB_DATE": "2025-01-02",
            "PNL": "",
            "COUNT": "11",
            "FLAG": "no",
            "LATE_COLUMN": "late",
        },
        {
            "DESK": "Credit",
            "COB_DATE": "2025-01-04",
            "PNL": "-2.25",
            "COUNT": "12",
            "FLAG": "true",
            "EMPTY_COLUMN": "",
        },
    ]

    profile = profile_source_rows(rows, source_name="client.csv", max_examples=2)

    assert profile.source_name == "client.csv"
    assert profile.row_count == 3
    assert [column.name for column in profile.columns] == [
        "DESK",
        "COB_DATE",
        "PNL",
        "COUNT",
        "FLAG",
        "LATE_COLUMN",
        "EMPTY_COLUMN",
    ]
    assert profile.column_count == 7
    assert profile.column("DESK").inferred_type == "string"
    assert profile.column("DESK").examples == ("Rates", "Credit")
    assert profile.column("COB_DATE").inferred_type == "date"
    assert profile.column("COB_DATE").min_value.isoformat() == "2025-01-02"
    assert profile.column("COB_DATE").max_value.isoformat() == "2025-01-04"
    assert profile.column("PNL").inferred_type == "float"
    assert profile.column("PNL").null_count == 1
    assert profile.column("PNL").null_rate == pytest.approx(1 / 3)
    assert profile.column("PNL").min_value == -2.25
    assert profile.column("PNL").max_value == 1200.5
    assert profile.column("COUNT").inferred_type == "integer"
    assert profile.column("COUNT").distinct_count == 3
    assert profile.column("FLAG").inferred_type == "boolean"
    assert profile.column("LATE_COLUMN").null_count == 2
    assert profile.column("EMPTY_COLUMN").inferred_type == "empty"
    assert profile.column("EMPTY_COLUMN").null_rate == 1.0
    assert len(profile.source_hash) == 64


def test_profile_csv_source_profiles_file_and_hashes_source_text(tmp_path) -> None:
    source = tmp_path / "source.csv"
    source.write_text(
        "desk,business_date,pnl\nRates,2025-01-02,1.0\nRates,2025-01-03,2.0\n",
        encoding="utf-8",
    )

    profile = profile_csv_source(source)

    assert profile.source_name == str(source)
    assert profile.row_count == 2
    assert profile.column("business_date").inferred_type == "date"
    assert profile.column("pnl").inferred_type == "float"
    assert len(profile.source_hash) == 64


def test_source_profile_as_dict_and_json_are_profile_json_ready() -> None:
    profile = profile_source_rows(
        [{"desk": "Rates", "business_date": "2025-01-02", "pnl": "1.0"}],
        source_name="rows",
    )

    payload = profile.as_dict()
    encoded = profile.to_json()

    assert payload["profile_schema"] == "ima-source-profile-v1"
    assert payload["row_count"] == 1
    assert json.loads(encoded) == payload


def test_profile_source_rows_rejects_negative_example_limit() -> None:
    with pytest.raises(ValueError, match="max_examples"):
        profile_source_rows([], max_examples=-1)
