from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest
from frtb_drc import calculate_drc_capital, result_json, validate_reconciliation

from tests.drc_fixture_helpers import assert_nested_close as _assert_nested_close

_FIXTURE_LOADER_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "drc_nonsec_v1" / "fixture_loader.py"
)


def test_nonsec_v1_fixture_matches_expected_stage_outputs() -> None:
    loader = _load_fixture_loader()
    result = calculate_drc_capital(loader.load_positions(), context=loader.load_context())
    expected = loader.load_expected_outputs()

    validate_reconciliation(result)
    actual = _selected_outputs(result)

    assert actual["fixture_id"] == expected["fixture_id"]
    assert actual["input_count"] == expected["input_count"]
    assert actual["input_hash"] == expected["input_hash"]
    assert actual["profile_hash"] == expected["profile_hash"]
    assert actual["gross"] == expected["gross"]
    assert actual["maturity_weights"] == expected["maturity_weights"]
    assert actual["scaled"] == expected["scaled"]
    assert actual["net"] == expected["net"]
    _assert_nested_close(actual["buckets"], expected["buckets"])
    assert actual["category_capital"] == pytest.approx(expected["category_capital"])
    assert actual["total_drc"] == pytest.approx(expected["total_drc"])
    assert actual["result_json_sha256"] == expected["result_json_sha256"]


def test_nonsec_v1_fixture_replays_deterministically() -> None:
    loader = _load_fixture_loader()
    positions = loader.load_positions()

    first = calculate_drc_capital(positions, context=loader.load_context())
    second = calculate_drc_capital(tuple(reversed(positions)), context=loader.load_context())

    assert result_json(first) == result_json(second)
    assert _selected_outputs(first) == _selected_outputs(second)


def test_nonsec_v1_fixture_docs_name_each_position_case() -> None:
    readme = (
        Path(__file__).resolve().parent / "fixtures" / "drc_nonsec_v1" / "README.md"
    ).read_text(encoding="utf-8")
    loader = _load_fixture_loader()

    for position in loader.load_positions():
        assert position.position_id in readme


def _load_fixture_loader() -> Any:
    spec = importlib.util.spec_from_file_location(
        "drc_nonsec_v1_fixture_loader",
        _FIXTURE_LOADER_PATH,
    )
    if spec is None or spec.loader is None:  # pragma: no cover - path is static.
        raise RuntimeError("could not load DRC non-sec fixture loader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _selected_outputs(result: Any) -> dict[str, object]:
    return {
        "fixture_id": "drc_nonsec_v1",
        "input_count": result.input_count,
        "input_hash": result.input_hash,
        "profile_hash": result.profile_hash,
        "gross": {record.position_id: record.gross_jtd for record in result.gross_jtds},
        "maturity_weights": {
            record.position_id: record.maturity_weight for record in result.maturity_scaled_jtds
        },
        "scaled": {record.position_id: record.scaled_jtd for record in result.maturity_scaled_jtds},
        "net": {
            record.net_jtd_id: {
                "amount": record.net_amount,
                "bucket": record.bucket_key,
                "direction": record.net_direction.value,
                "issuer": record.obligor_or_tranche_key,
                "rejected_offsets": [offset.reason_code for offset in record.rejected_offsets],
            }
            for record in result.net_jtds
        },
        "buckets": {
            bucket.bucket_key: {
                "capital": bucket.capital,
                "floor_applied": bucket.floor_applied,
                "hbr": bucket.hbr.ratio,
                "weighted_long": bucket.weighted_long,
                "weighted_short": bucket.weighted_short,
            }
            for bucket in result.categories[0].bucket_results
        },
        "category_capital": result.categories[0].capital,
        "total_drc": result.total_drc,
        "result_json_sha256": hashlib.sha256(result_json(result).encode()).hexdigest(),
    }
