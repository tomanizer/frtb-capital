from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from frtb_cva import calculate_cva_capital, validate_cva_result_reconciliation
from frtb_cva.hedges import eligible_sa_cva_hedge_ids
from frtb_cva.weighted_sensitivity import (
    compute_weighted_sensitivities,
    sort_weighted_sensitivities,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sa_cva_girr_delta_v1"

_loader_spec = importlib.util.spec_from_file_location(
    "sa_cva_girr_delta_v1_loader",
    FIXTURE_DIR / "loader.py",
)
_loader_module = importlib.util.module_from_spec(_loader_spec)  # type: ignore[arg-type]
_loader_spec.loader.exec_module(_loader_module)  # type: ignore[union-attr]
load_expected_outputs = _loader_module.load_expected_outputs
load_fixture_cases = _loader_module.load_fixture_cases
load_fixture_context = _loader_module.load_fixture_context
load_invalid_cases = _loader_module.load_invalid_cases


def test_fixture_cases_match_expected_outputs() -> None:
    context = load_fixture_context()
    expected = load_expected_outputs()
    assert set(expected) == {case_id for case_id, _, _ in load_fixture_cases()}

    for case_id, sensitivities, hedges in load_fixture_cases():
        result = calculate_cva_capital(
            context,
            (),
            (),
            sensitivities=sensitivities,
            hedges=hedges,
        )
        case_expected = expected[case_id]
        assert result.total_cva_capital == pytest.approx(case_expected["total_cva_capital"])
        assert result.input_hash == case_expected["input_hash"]
        _assert_payload_matches(
            _weighted_sensitivity_payload(_weighted_sensitivities(context, sensitivities, hedges)),
            case_expected["weighted_sensitivities"],
        )
        _assert_payload_matches(
            _risk_class_capital_payload(result.sa_cva_risk_class_capitals),
            case_expected["sa_cva_risk_class_capitals"],
        )
        validate_cva_result_reconciliation(result)


def test_invalid_fixture_cases_fail_before_capital() -> None:
    context = load_fixture_context()
    for _, expected_match, sensitivities, hedges in load_invalid_cases():
        with pytest.raises(Exception, match=expected_match):
            calculate_cva_capital(
                context,
                (),
                (),
                sensitivities=sensitivities,
                hedges=hedges,
            )


def test_fixture_cases_are_deterministic() -> None:
    context = load_fixture_context()
    for case_id, sensitivities, hedges in load_fixture_cases():
        first = calculate_cva_capital(
            context,
            (),
            (),
            sensitivities=sensitivities,
            hedges=hedges,
        )
        second = calculate_cva_capital(
            context,
            (),
            (),
            sensitivities=sensitivities,
            hedges=hedges,
        )
        assert first.as_dict() == second.as_dict(), case_id
        first_weighted = _weighted_sensitivity_payload(
            _weighted_sensitivities(context, sensitivities, hedges)
        )
        second_weighted = _weighted_sensitivity_payload(
            _weighted_sensitivities(context, sensitivities, hedges)
        )
        assert first_weighted == second_weighted, case_id


def test_offsetting_hedge_fixture_preserves_gross_and_net_amounts() -> None:
    expected = load_expected_outputs()["offsetting_hedge"]["weighted_sensitivities"][0]
    assert expected["gross_cva_amount"] == pytest.approx(1_000_000.0)
    assert expected["gross_hedge_amount"] == pytest.approx(1_000_000.0)
    assert expected["net_amount"] == pytest.approx(0.0)
    assert expected["weighted_cva"] == pytest.approx(expected["weighted_hedge"])
    assert expected["weighted_net"] == pytest.approx(0.0)


def test_ineligible_hedge_fixture_drops_hedge_benefit() -> None:
    expected = load_expected_outputs()["ineligible_hedge_rejected"]
    weighted = expected["weighted_sensitivities"][0]
    bucket = expected["sa_cva_risk_class_capitals"][0]["bucket_capitals"][0]
    assert weighted["gross_cva_amount"] == pytest.approx(1_000_000.0)
    assert weighted["gross_hedge_amount"] == pytest.approx(0.0)
    assert weighted["source_sensitivity_ids"] == ["sens-usd-5y-ineligible-cva"]
    assert bucket["sensitivity_ids"] == ["sens-usd-5y-ineligible-cva"]


def _weighted_sensitivities(context: Any, sensitivities: Any, hedges: Any) -> tuple[Any, ...]:
    return sort_weighted_sensitivities(
        compute_weighted_sensitivities(
            sensitivities,
            hedges=hedges,
            eligible_hedge_ids=eligible_sa_cva_hedge_ids(hedges),
            reporting_currency=context.base_currency,
            profile=context.profile,
        )
    )


def _weighted_sensitivity_payload(weighted_sensitivities: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            "risk_class": item.risk_factor_key.risk_class.value,
            "risk_measure": item.risk_factor_key.risk_measure.value,
            "bucket_id": item.risk_factor_key.bucket_id,
            "risk_factor_key": item.risk_factor_key.risk_factor_key,
            "tenor": item.risk_factor_key.tenor,
            "gross_cva_amount": item.gross_cva_amount,
            "gross_hedge_amount": item.gross_hedge_amount,
            "net_amount": item.net_amount,
            "risk_weight": item.risk_weight,
            "weighted_cva": item.weighted_cva,
            "weighted_hedge": item.weighted_hedge,
            "weighted_net": item.weighted_net,
            "source_sensitivity_ids": list(item.source_sensitivity_ids),
            "citations": list(item.citations),
        }
        for item in weighted_sensitivities
    ]


def _risk_class_capital_payload(risk_class_capitals: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            "risk_class": item.risk_class.value,
            "risk_measure": item.risk_measure.value,
            "pre_multiplier_capital": item.pre_multiplier_capital,
            "post_multiplier_capital": item.post_multiplier_capital,
            "m_cva": item.m_cva,
            "citations": list(item.citations),
            "bucket_capitals": [
                {
                    "bucket_id": bucket.bucket_id,
                    "risk_class": bucket.risk_class.value,
                    "risk_measure": bucket.risk_measure.value,
                    "k_b": bucket.k_b,
                    "s_b": bucket.s_b,
                    "sensitivity_ids": list(bucket.sensitivity_ids),
                    "citations": list(bucket.citations),
                    "branch_metadata": [list(pair) for pair in bucket.branch_metadata],
                }
                for bucket in item.bucket_capitals
            ],
        }
        for item in risk_class_capitals
    ]


def _assert_payload_matches(actual: Any, expected: Any) -> None:
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        assert isinstance(actual, int | float) and not isinstance(actual, bool)
        assert actual == pytest.approx(expected)
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert actual.keys() == expected.keys()
        for key, expected_value in expected.items():
            _assert_payload_matches(actual[key], expected_value)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_value, expected_value in zip(actual, expected, strict=True):
            _assert_payload_matches(actual_value, expected_value)
        return
    assert actual == expected
