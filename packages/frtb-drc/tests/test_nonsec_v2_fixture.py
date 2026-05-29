from __future__ import annotations

import hashlib

import pytest
from frtb_drc import calculate_drc_capital, result_json, validate_reconciliation
from frtb_drc.demo_fixture import load_drc_nonsec_v2_fixture


def test_nonsec_v2_fixture_matches_expected_stage_outputs() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    result = calculate_drc_capital(fixture.positions, context=fixture.context)
    expected = fixture.expected_outputs

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


def test_nonsec_v2_fixture_replays_deterministically() -> None:
    fixture = load_drc_nonsec_v2_fixture()

    first = calculate_drc_capital(fixture.positions, context=fixture.context)
    second = calculate_drc_capital(tuple(reversed(fixture.positions)), context=fixture.context)

    assert result_json(first) == result_json(second)
    assert _selected_outputs(first) == _selected_outputs(second)


def test_nonsec_v2_fixture_has_expected_bucket_coverage() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    buckets = {p.bucket_key for p in fixture.positions}
    assert buckets == {"CORPORATE", "NON_US_SOVEREIGN", "PSE_GSE", "DEFAULTED"}


def test_nonsec_v2_fixture_has_expected_position_count() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    assert fixture.expected_outputs["input_count"] == 40


def _assert_nested_close(actual: object, expected: object) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert actual.keys() == expected.keys()
        for key, expected_value in expected.items():
            _assert_nested_close(actual[key], expected_value)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_value, expected_value in zip(actual, expected, strict=True):
            _assert_nested_close(actual_value, expected_value)
        return
    if isinstance(expected, float):
        assert actual == pytest.approx(expected)
        return
    assert actual == expected


def _selected_outputs(result: object) -> dict[str, object]:
    return {
        "fixture_id": "drc_nonsec_v2",
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
