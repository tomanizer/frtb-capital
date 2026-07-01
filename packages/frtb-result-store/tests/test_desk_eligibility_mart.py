"""Tests for the PLA/backtesting desk eligibility mart."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from fixtures.capital_navigator_bundle import capital_navigator_bundle
from fixtures.result_store_bundle import run_with_id
from frtb_result_store import DuckDbParquetResultStore, create_result_store_app
from frtb_result_store._model_desk_eligibility import (
    BacktestingState,
    DeskEligibilityRow,
    DeskEligibilityState,
    PLAState,
)
from frtb_result_store.desk_eligibility_rows import (
    _desk_eligibility_mart_from_row,
    _desk_eligibility_mart_row,
)
from frtb_result_store.mart_schemas import (
    MART_NAMES,
    MART_SCHEMA_VERSION,
    MART_SCHEMAS,
    mart_schema_fingerprint,
)


def test_desk_eligibility_schema_is_registered() -> None:
    assert "desk_eligibility" in MART_NAMES
    assert MART_SCHEMA_VERSION >= 6

    schema = MART_SCHEMAS["desk_eligibility"]
    assert [field.name for field in schema] == [
        "run_id",
        "desk_id",
        "desk_node_id",
        "label",
        "legal_entity_id",
        "division_id",
        "business_line_id",
        "volcker_desk_id",
        "book_ids_json",
        "eligibility_state",
        "pla_state",
        "pla_threshold_profile_id",
        "pla_metric_summary_json",
        "backtesting_state",
        "backtesting_zone",
        "backtesting_exception_count",
        "backtesting_window",
        "latest_exception_date",
        "rfet_modellable_count",
        "nmrf_count",
        "ses_amount",
        "capital_consequence_amount",
        "capital_consequence_currency",
        "capital_node_id",
        "pnl_artifact_id",
        "rfet_artifact_id",
        "source_artifact_id",
        "model_run_id",
        "profile_hash",
        "source_hashes_json",
        "calculation_timestamp",
        "metadata_json",
    ]
    assert mart_schema_fingerprint("desk_eligibility") == mart_schema_fingerprint(
        "desk_eligibility"
    )


def test_desk_eligibility_row_round_trip() -> None:
    row = DeskEligibilityRow(
        run_id="run-1",
        desk_id="rates",
        desk_node_id="ima-rates-desk",
        label="Rates desk",
        legal_entity_id="le-demo",
        division_id="markets",
        business_line_id="ficc",
        volcker_desk_id="volcker-rates",
        book_ids=("rates-core",),
        eligibility_state=DeskEligibilityState.ELIGIBLE,
        pla_state=PLAState.PASSING,
        pla_threshold_profile_id="pla-profile-us-npr-2026",
        pla_metric_summary={"spearman": 0.91},
        backtesting_state=BacktestingState.GREEN,
        backtesting_zone="green",
        backtesting_exception_count=1,
        backtesting_window="250d",
        latest_exception_date=date(2026, 5, 21),
        rfet_modellable_count=18,
        nmrf_count=2,
        ses_amount=12.0,
        capital_consequence_amount=42.0,
        capital_consequence_currency="USD",
        capital_node_id="ima-rates-desk",
        pnl_artifact_id="navigator-ima-pnl-vector",
        rfet_artifact_id="navigator-rfet-observation-timeline",
        source_artifact_id="navigator-ima-pnl-vector",
        model_run_id="run-1",
        profile_hash="profile-hash",
        source_hashes=("hpl-hash", "rtpl-hash"),
        calculation_timestamp=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )

    storage_row = _desk_eligibility_mart_row(row)
    decoded = _desk_eligibility_mart_from_row(tuple(storage_row.values()))

    assert decoded == row


def test_capital_navigator_fixture_populates_desk_eligibility_mart(
    tmp_path: Path,
) -> None:
    store, run_id = _write_fixture(tmp_path)

    page = store.list_desk_eligibility(run_id)
    rows = page["items"]
    assert page["state"] == "available"
    assert page["total_count"] == 3

    by_desk = {row.desk_id: row for row in rows}
    assert by_desk["rates"].eligibility_state is DeskEligibilityState.ELIGIBLE
    assert by_desk["rates"].pla_state is PLAState.PASSING
    assert by_desk["rates"].backtesting_state is BacktestingState.GREEN
    assert by_desk["rates"].book_ids == ("rates-core",)
    assert by_desk["rates"].pnl_artifact_id == "navigator-ima-pnl-vector"
    assert by_desk["rates"].rfet_artifact_id == "navigator-rfet-observation-timeline"
    assert by_desk["rates"].capital_consequence_amount == 42.0
    assert by_desk["rates"].ses_amount == 12.0

    assert by_desk["credit"].eligibility_state is DeskEligibilityState.AMBER
    assert by_desk["credit"].backtesting_exception_count == 6

    assert by_desk["equity"].eligibility_state is DeskEligibilityState.NOT_RUN
    assert by_desk["equity"].pla_state is PLAState.NO_DATA
    assert by_desk["equity"].backtesting_state is BacktestingState.NOT_RUN
    assert by_desk["equity"].capital_consequence_amount is None


def test_desk_eligibility_filters_and_no_data_detail(tmp_path: Path) -> None:
    store, run_id = _write_fixture(tmp_path)

    amber = store.list_desk_eligibility(run_id, eligibility_state="amber")["items"]
    assert [row.desk_id for row in amber] == ["credit"]

    ficc = store.list_desk_eligibility(run_id, hierarchy_node_id="ficc")["items"]
    assert [row.desk_id for row in ficc] == ["credit", "rates"]

    rates = store.get_desk_eligibility(run_id, "rates")
    assert rates["state"] == "available"
    assert rates["eligibility"].desk_node_id == "ima-rates-desk"

    missing = store.get_desk_eligibility(run_id, "missing")
    assert missing == {"state": "no_data", "desk_id": "missing", "eligibility": None}


def test_desk_eligibility_api_payload(tmp_path: Path) -> None:
    store, run_id = _write_fixture(tmp_path)
    client = TestClient(create_result_store_app(store))

    response = client.get(
        f"/runs/{run_id}/desk-eligibility",
        params={"pla_state": "amber", "limit": 10},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["total_count"] == 1
    assert payload["items"][0]["desk_id"] == "credit"
    assert payload["items"][0]["source_hashes"] == ["hpl-credit-hash", "rtpl-credit-hash"]

    detail = client.get(f"/runs/{run_id}/desk-eligibility/equity").json()
    assert detail["state"] == "available"
    assert detail["eligibility"]["eligibility_state"] == "not_run"
    assert detail["eligibility"]["source_artifact_id"] == (
        "navigator-rfet-observation-timeline-no-data"
    )


def _write_fixture(tmp_path: Path) -> tuple[DuckDbParquetResultStore, str]:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    run = run_with_id("frtb/capital-navigator/2026-06-03/us-npr")
    bundle = capital_navigator_bundle(run=run, artifact_root=store.root / "navigator-artifacts")
    store.write_bundle(bundle)
    return store, run.run_id
