from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmInputError,
    calculate_sbm_capital,
    serialize_sbm_result,
    validate_sbm_result_reconciliation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "girr_delta_v1"
_RISK_CLASS_KEYS = ("risk_class", "risk_measure", "selected_capital", "selected_scenario")
_BUCKET_KEYS = ("bucket_id", "kb", "sb")
_WEIGHTED_KEYS = ("sensitivity_id", "risk_weight", "scaled_amount")


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("girr_delta_v1_loader", FIXTURE_DIR / "loader.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_non_girr_vega_fixture_module() -> ModuleType:
    fixture_dir = Path(__file__).parent / "fixtures" / "non_girr_vega_v1"
    spec = importlib.util.spec_from_file_location(
        "non_girr_vega_v1_loader",
        fixture_dir / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_girr_delta_v1_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_capital"] == expected["total_capital"]
    assert payload["warnings"] == expected["warnings"]
    risk_class_payload = [
        _select(risk_class, _RISK_CLASS_KEYS) for risk_class in payload["risk_classes"]
    ]
    assert risk_class_payload == expected["risk_classes"]
    assert [
        [_select(bucket, _BUCKET_KEYS) for bucket in risk_class["buckets"]]
        for risk_class in payload["risk_classes"]
    ] == expected["buckets"]
    assert [
        [
            [_select(item, _WEIGHTED_KEYS) for item in bucket["weighted_sensitivities"]]
            for bucket in risk_class["buckets"]
        ]
        for risk_class in payload["risk_classes"]
    ] == expected["weighted_sensitivities"]


def test_girr_delta_v1_fixture_result_is_replay_stable() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()

    first = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))
    second = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=context))

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_girr_vega_v1_fixture_matches_expected_outputs() -> None:
    vega_fixture_dir = Path(__file__).parent / "fixtures" / "girr_vega_v1"
    spec = importlib.util.spec_from_file_location(
        "girr_vega_v1_loader",
        vega_fixture_dir / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = module.load_fixture_context()
    sensitivities = module.load_fixture_sensitivities()
    expected = module.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["total_capital"] == expected["total_capital"]


def test_fx_delta_v1_fixture_matches_expected_outputs() -> None:
    """Replay fx_delta_v1 through the public API and compare audit payloads.

    Deterministic under CPython 3.11; relies on stable fixture ordering only.
    """
    fx_fixture_dir = Path(__file__).parent / "fixtures" / "fx_delta_v1"
    spec = importlib.util.spec_from_file_location(
        "fx_delta_v1_loader",
        fx_fixture_dir / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = module.load_fixture_context()
    sensitivities = module.load_fixture_sensitivities()
    expected = module.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["total_capital"] == expected["total_capital"]


def test_equity_delta_v1_fixture_matches_expected_outputs() -> None:
    equity_fixture_dir = Path(__file__).parent / "fixtures" / "equity_delta_v1"
    spec = importlib.util.spec_from_file_location(
        "equity_delta_v1_loader",
        equity_fixture_dir / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = module.load_fixture_context()
    sensitivities = module.load_fixture_sensitivities()
    expected = module.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["total_capital"] == expected["total_capital"]


def test_commodity_delta_v1_fixture_matches_expected_outputs() -> None:
    commodity_fixture_dir = Path(__file__).parent / "fixtures" / "commodity_delta_v1"
    spec = importlib.util.spec_from_file_location(
        "commodity_delta_v1_loader",
        commodity_fixture_dir / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = module.load_fixture_context()
    sensitivities = module.load_fixture_sensitivities()
    expected = module.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["total_capital"] == expected["total_capital"]


def test_non_girr_vega_v1_fixture_matches_expected_outputs() -> None:
    module = load_non_girr_vega_fixture_module()
    context = module.load_fixture_context()
    sensitivities = module.load_fixture_sensitivities()
    expected = module.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    validate_sbm_result_reconciliation(result)
    payload = serialize_sbm_result(result)

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_capital"] == expected["total_capital"]
    assert payload["warnings"] == expected["warnings"]
    assert payload["selected_portfolio_scenario"] == expected["selected_portfolio_scenario"]
    assert payload["portfolio_scenario_totals"] == expected["portfolio_scenario_totals"]
    assert [
        _select(risk_class, _RISK_CLASS_KEYS) for risk_class in payload["risk_classes"]
    ] == expected["risk_classes"]
    assert [risk_class["scenario_totals"] for risk_class in payload["risk_classes"]] == expected[
        "risk_class_scenario_totals"
    ]
    assert [
        [_select(bucket, _BUCKET_KEYS) for bucket in risk_class["buckets"]]
        for risk_class in payload["risk_classes"]
    ] == expected["buckets"]
    assert [
        [
            [_select(item, _WEIGHTED_KEYS) for item in bucket["weighted_sensitivities"]]
            for bucket in risk_class["buckets"]
        ]
        for risk_class in payload["risk_classes"]
    ] == expected["weighted_sensitivities"]


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_non_girr_vega_fixture_module().load_invalid_cases(),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_non_girr_vega_v1_invalid_fixture_cases_fail(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_non_girr_vega_fixture_module()
    context = loader.load_fixture_context()

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_fixture_module().load_invalid_cases(),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_girr_delta_v1_invalid_fixture_cases_fail(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id


def _select(payload: object, keys: tuple[str, ...]) -> dict[str, object]:
    assert isinstance(payload, dict)
    return {key: payload[key] for key in keys}
