from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest
from frtb_cva import calculate_cva_capital, validate_cva_result_reconciliation

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
        validate_cva_result_reconciliation(result)


def test_invalid_fixture_cases_fail_before_capital() -> None:
    context = load_fixture_context()
    for case_id, expected_match, sensitivities, hedges in load_invalid_cases():
        with pytest.raises(Exception, match=expected_match):
            calculate_cva_capital(
                context,
                (),
                (),
                sensitivities=sensitivities,
                hedges=hedges,
            )


def test_fixture_cases_are_pairwise_distinct() -> None:
    context = load_fixture_context()
    totals: list[float] = []
    for case_id, sensitivities, hedges in load_fixture_cases():
        result = calculate_cva_capital(
            context,
            (),
            (),
            sensitivities=sensitivities,
            hedges=hedges,
        )
        assert result.total_cva_capital > 0.0, case_id
        totals.append(result.total_cva_capital)
    assert len(set(totals)) == len(totals)
