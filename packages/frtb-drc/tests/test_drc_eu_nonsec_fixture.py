from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pytest
from frtb_common import source_content_hash
from frtb_drc import (
    DrcCalculationContext,
    DrcPosition,
    DrcSourceLineage,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    result_json,
    validate_reconciliation,
)
from frtb_drc.arrow_batch import build_drc_nonsec_batch_from_arrow, normalize_drc_nonsec_arrow_table

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "drc_eu_nonsec_v1"


def test_eu_crr3_nonsec_fixture_matches_expected_stage_outputs() -> None:
    fixture = _load_fixture()
    result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    expected = fixture["expected"]

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
    assert actual["citations"] == tuple(expected["citations"])
    assert actual["result_json_sha256"] == expected["result_json_sha256"]


def test_eu_crr3_nonsec_arrow_batch_matches_row_result() -> None:
    fixture = _load_fixture()
    row_result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    handoff = normalize_drc_nonsec_arrow_table(
        _arrow_table(fixture["positions"]),
        source_hash=source_content_hash("synthetic eu drc nonsec source"),
    )

    batch = build_drc_nonsec_batch_from_arrow(handoff, profile_id="EU_CRR3")
    calculation = calculate_drc_capital_from_batch(batch, context=fixture["context"])

    validate_reconciliation(calculation.result)
    assert calculation.result.profile_id == "EU_CRR3"
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    assert "EU_CRR3_ECAI_CQS_MAPPING" in calculation.result.citations
    assert not any(citation.startswith("US_NPR") for citation in calculation.result.citations)
    assert not any(citation.startswith("BASEL_MAR22") for citation in calculation.result.citations)


def test_eu_crr3_nonsec_fixture_docs_name_each_position_case() -> None:
    readme = (_FIXTURE_DIR / "README.md").read_text(encoding="utf-8")
    fixture = _load_fixture()

    for position in fixture["positions"]:
        assert position.position_id in readme


def _load_fixture() -> dict[str, Any]:
    payload = json.loads((_FIXTURE_DIR / "positions.json").read_text(encoding="utf-8"))
    context_payload = payload["context"]
    context = DrcCalculationContext(
        run_id=context_payload["run_id"],
        calculation_date=date.fromisoformat(context_payload["calculation_date"]),
        base_currency=context_payload["base_currency"],
        profile_id=context_payload["profile_id"],
    )
    positions = []
    for raw_position in payload["positions"]:
        position = dict(raw_position)
        position["lineage"] = DrcSourceLineage(**position["lineage"])
        positions.append(DrcPosition(**position))
    expected = json.loads((_FIXTURE_DIR / "expected_outputs.json").read_text(encoding="utf-8"))
    return {"context": context, "positions": tuple(positions), "expected": expected}


def _selected_outputs(result: Any) -> dict[str, object]:
    return {
        "fixture_id": "drc_eu_nonsec_v1",
        "input_count": result.input_count,
        "input_hash": result.input_hash,
        "profile_hash": result.profile_hash,
        "gross": {record.position_id: record.gross_jtd for record in result.gross_jtds},
        "maturity_weights": {
            record.position_id: record.maturity_weight for record in result.maturity_scaled_jtds
        },
        "scaled": {record.position_id: record.scaled_jtd for record in result.maturity_scaled_jtds},
        "net": _net_outputs(result.net_jtds),
        "buckets": _bucket_outputs(result.categories[0].bucket_results),
        "category_capital": result.categories[0].capital,
        "total_drc": result.total_drc,
        "citations": result.citations,
        "result_json_sha256": hashlib.sha256(bytes(result_json(result), "utf-8")).hexdigest(),
    }


def _net_outputs(net_jtds: tuple[Any, ...]) -> dict[str, dict[str, object]]:
    return {
        record.net_jtd_id: {
            "amount": record.net_amount,
            "bucket": record.bucket_key,
            "direction": record.net_direction.value,
            "issuer": record.obligor_or_tranche_key,
            "rejected_offsets": [offset.reason_code for offset in record.rejected_offsets],
        }
        for record in net_jtds
    }


def _bucket_outputs(bucket_results: tuple[Any, ...]) -> dict[str, dict[str, object]]:
    return {
        bucket.bucket_key: {
            "capital": bucket.capital,
            "floor_applied": bucket.floor_applied,
            "hbr": bucket.hbr.ratio,
            "weighted_long": bucket.weighted_long,
            "weighted_short": bucket.weighted_short,
        }
        for bucket in bucket_results
    }


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


def _arrow_table(positions: tuple[DrcPosition, ...]) -> pa.Table:
    rows = []
    for position in positions:
        rows.append(
            {
                "position_id": position.position_id,
                "source_row_id": position.source_row_id,
                "desk_id": position.desk_id,
                "legal_entity": position.legal_entity,
                "risk_class": position.risk_class.value,
                "instrument_type": position.instrument_type.value,
                "default_direction": position.default_direction.value,
                "issuer_id": position.issuer_id,
                "tranche_id": position.tranche_id,
                "index_series_id": position.index_series_id,
                "bucket_key": position.bucket_key,
                "seniority": position.seniority.value if position.seniority is not None else None,
                "credit_quality": (
                    position.credit_quality.value if position.credit_quality is not None else None
                ),
                "notional": position.notional,
                "market_value": position.market_value,
                "cumulative_pnl": position.cumulative_pnl,
                "maturity_years": position.maturity_years,
                "currency": position.currency,
                "citation_ids": ",".join(position.citation_ids),
                "lineage_source_system": position.lineage.source_system
                if position.lineage is not None
                else "",
                "lineage_source_file": position.lineage.source_file
                if position.lineage is not None
                else "",
                "lineage_source_row_id": position.lineage.source_row_id
                if position.lineage is not None
                else "",
                "lineage_source_column_map": json.dumps(
                    _source_column_map(position),
                    sort_keys=True,
                ),
            }
        )
    return pa.Table.from_pylist(cast(list[dict[str, object]], rows))


def _source_column_map(position: DrcPosition) -> dict[str, str]:
    if position.lineage is None:
        return {}
    return dict(position.lineage.source_column_map)
