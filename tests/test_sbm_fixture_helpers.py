"""Tests for shared SBM fixture helper validation."""

from __future__ import annotations

import pytest

from tests.sbm_fixture_helpers import (
    load_sbm_fixture_context,
    load_sbm_invalid_cases,
    sbm_sensitivity_from_payload,
)


def test_load_sbm_fixture_context_rejects_missing_context() -> None:
    with pytest.raises(ValueError, match="Missing 'context' key"):
        load_sbm_fixture_context({})


def test_load_sbm_fixture_context_rejects_missing_context_field() -> None:
    with pytest.raises(ValueError, match="Missing 'run_id' key"):
        load_sbm_fixture_context({"context": {}})


def test_sbm_sensitivity_from_payload_preserves_configured_lineage_order() -> None:
    sensitivity = sbm_sensitivity_from_payload(
        _sensitivity_payload(),
        text_fields=("tenor", "option_tenor"),
        int_fields=("liquidity_horizon_days",),
        float_fields=("up_shock_amount", "down_shock_amount"),
    )

    assert sensitivity.tenor == "1y"
    assert sensitivity.option_tenor == "3m"
    assert sensitivity.liquidity_horizon_days == 20
    assert sensitivity.up_shock_amount == 125.0
    assert sensitivity.down_shock_amount == -125.0
    assert sensitivity.lineage.source_column_map == (
        ("amount", "amount"),
        ("tenor", "tenor"),
        ("option_tenor", "option_tenor"),
    )


def test_load_sbm_invalid_cases_handles_optional_duplicate_payload() -> None:
    cases = load_sbm_invalid_cases(
        [
            {
                "case_id": "duplicate_sensitivity_id",
                "expected_error_match": "duplicate sensitivity id",
                "sensitivity": _sensitivity_payload("dup-1", "row-1"),
                "duplicate_of": _sensitivity_payload("dup-1", "row-2"),
            },
            {
                "case_id": "single_bad_case",
                "expected_error_match": "missing tenor",
                "sensitivity": _sensitivity_payload("bad-1", "row-3"),
            },
        ],
        lambda payload: sbm_sensitivity_from_payload(payload, text_fields=("tenor",)),
    )

    assert cases[0][0] == "duplicate_sensitivity_id"
    assert cases[0][1] == "duplicate sensitivity id"
    assert [sensitivity.source_row_id for sensitivity in cases[0][2]] == ["row-1", "row-2"]
    assert cases[1][0] == "single_bad_case"
    assert len(cases[1][2]) == 1


def _sensitivity_payload(
    sensitivity_id: str = "eur-1y",
    source_row_id: str = "row-001",
) -> dict[str, object]:
    return {
        "sensitivity_id": sensitivity_id,
        "source_row_id": source_row_id,
        "desk_id": "rates-desk",
        "legal_entity": "LE-001",
        "risk_class": "GIRR",
        "risk_measure": "DELTA",
        "bucket": "1",
        "risk_factor": "EUR",
        "amount": 1000000.0,
        "amount_currency": "USD",
        "tenor": "1y",
        "option_tenor": "3m",
        "liquidity_horizon_days": "20",
        "up_shock_amount": "125.0",
        "down_shock_amount": "-125.0",
        "sign_convention": "RECEIVE",
        "mapping_citation_ids": ("MAR21.4",),
    }
