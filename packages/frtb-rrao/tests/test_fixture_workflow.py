from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from frtb_rrao import (
    RraoInputError,
    calculate_rrao_capital,
    serialize_rrao_result,
    validate_rrao_result_reconciliation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rrao_v1"
_LINE_KEYS = ("position_id", "classification", "risk_weight", "add_on", "reason_code", "citations")
_EXCLUDED_LINE_KEYS = (
    "position_id",
    "exclusion_reason",
    "add_on",
    "reason_code",
    "citations",
)
_SUBTOTAL_KEYS = ("subtotal_type", "subtotal_key", "gross_effective_notional", "add_on")


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rrao_v1_loader", FIXTURE_DIR / "loader.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rrao_v1_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    positions = loader.load_fixture_positions()
    expected = loader.load_expected_outputs()

    result = calculate_rrao_capital(positions, context=context)
    validate_rrao_result_reconciliation(result)
    payload = serialize_rrao_result(result)

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_rrao"] == expected["total_rrao"]
    assert payload["warnings"] == expected["warnings"]
    assert payload["citations"] == expected["citations"]
    assert [_select(line, _LINE_KEYS) for line in payload["lines"]] == expected["included_lines"]
    assert [_select(line, _EXCLUDED_LINE_KEYS) for line in payload["excluded_lines"]] == expected[
        "excluded_lines"
    ]
    assert [_select(subtotal, _SUBTOTAL_KEYS) for subtotal in payload["subtotals"]] == expected[
        "subtotals"
    ]


def test_rrao_v1_fixture_result_is_replay_stable() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    positions = loader.load_fixture_positions()

    first = serialize_rrao_result(calculate_rrao_capital(positions, context=context))
    second = serialize_rrao_result(calculate_rrao_capital(positions, context=context))

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "position"),
    load_fixture_module().load_invalid_cases(),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_rrao_v1_invalid_fixture_cases_fail(
    case_id: str,
    expected_error_match: str,
    position: object,
) -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()

    with pytest.raises(RraoInputError, match=expected_error_match):
        calculate_rrao_capital((position,), context=context)
    assert case_id


def _select(payload: object, keys: tuple[str, ...]) -> dict[str, object]:
    assert isinstance(payload, dict)
    return {key: payload[key] for key in keys}
