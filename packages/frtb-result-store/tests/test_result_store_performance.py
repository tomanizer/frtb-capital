from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from fastapi.testclient import TestClient
from frtb_result_store import create_result_store_app
from test_result_store_api import _store_with_drillthrough_artifact


def test_representative_dashboard_query_latency_fixture(tmp_path) -> None:
    store, run, artifact = _store_with_drillthrough_artifact(tmp_path)
    client = TestClient(create_result_store_app(store))

    timings_ms = {
        "capital_summary": _elapsed_ms(lambda: store.capital_summary(run.run_id)),
        "capital_tree": _elapsed_ms(lambda: store.capital_tree(run.run_id)),
        "top_contributors": _elapsed_ms(lambda: store.top_contributors(run.run_id, limit=10)),
        "artifact_first_page": _elapsed_ms(
            lambda: client.get(
                f"/runs/{run.run_id}/artifacts/{artifact.artifact_id}/page",
                params={"limit": 1},
            )
        ),
    }

    assert timings_ms["capital_summary"] < 250.0
    assert timings_ms["capital_tree"] < 250.0
    assert timings_ms["top_contributors"] < 250.0
    assert timings_ms["artifact_first_page"] < 1000.0


def _elapsed_ms(callback: Callable[[], object]) -> float:
    started = perf_counter()
    callback()
    return (perf_counter() - started) * 1000.0
