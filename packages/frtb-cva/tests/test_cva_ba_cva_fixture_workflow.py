from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest
from frtb_cva import calculate_cva_capital

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ba_cva_reduced_v1"

_loader_spec = importlib.util.spec_from_file_location(
    "ba_cva_reduced_v1_loader",
    FIXTURE_DIR / "loader.py",
)
_loader_module = importlib.util.module_from_spec(_loader_spec)  # type: ignore[arg-type]
_loader_spec.loader.exec_module(_loader_module)  # type: ignore[union-attr]
load_expected_outputs = _loader_module.load_expected_outputs
load_fixture_cases = _loader_module.load_fixture_cases
load_fixture_context = _loader_module.load_fixture_context
load_invalid_cases = _loader_module.load_invalid_cases


def test_fixture_cases_match_independent_challenger_outputs() -> None:
    context = load_fixture_context()
    expected = load_expected_outputs()
    assert set(expected) == {case_id for case_id, _, _ in load_fixture_cases()}

    for case_id, counterparties, netting_sets in load_fixture_cases():
        result = calculate_cva_capital(context, counterparties, netting_sets)
        case_expected = expected[case_id]
        assert result.total_cva_capital == pytest.approx(case_expected["k_reduced"])
        assert result.ba_cva_reduced is not None
        _assert_reduced_result_matches(result.ba_cva_reduced, case_expected)


def test_invalid_fixture_cases_fail_before_capital() -> None:
    context = load_fixture_context()
    for case_id, expected_match, counterparties, netting_sets in load_invalid_cases():
        with pytest.raises(Exception, match=expected_match):
            calculate_cva_capital(context, counterparties, netting_sets)


def test_fixture_cases_are_deterministic() -> None:
    context = load_fixture_context()
    for case_id, counterparties, netting_sets in load_fixture_cases():
        first = calculate_cva_capital(context, counterparties, netting_sets)
        second = calculate_cva_capital(context, counterparties, netting_sets)
        assert first.as_dict() == second.as_dict(), case_id


def test_package_does_not_import_sibling_capital_packages() -> None:
    forbidden_prefixes = (
        "frtb_rrao",
        "frtb_sbm",
        "frtb_drc",
        "frtb_ima",
        "frtb_orchestration",
    )
    package = importlib.import_module("frtb_cva")
    for module_name in (
        "frtb_cva.data_models",
        "frtb_cva.validation",
        "frtb_cva.reference_data",
        "frtb_cva.regimes",
        "frtb_cva.scope",
        "frtb_cva.ba_cva",
        "frtb_cva.capital",
        "frtb_cva.audit",
        "frtb_cva.sa_cva",
        "frtb_cva.aggregation",
        "frtb_cva.weighted_sensitivity",
    ):
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding="utf-8")
        for prefix in forbidden_prefixes:
            assert prefix not in source
    assert package.__name__ == "frtb_cva"


def _assert_reduced_result_matches(actual: Any, expected: dict[str, Any]) -> None:
    assert actual.rho == pytest.approx(expected["rho"])
    assert actual.d_ba_cva == pytest.approx(expected["d_ba_cva"])
    assert actual.alpha == pytest.approx(expected["alpha"])
    assert actual.sum_scva == pytest.approx(expected["sum_scva"])
    assert actual.k_portfolio == pytest.approx(expected["k_portfolio"])
    assert actual.k_reduced == pytest.approx(expected["k_reduced"])

    actual_lines = sorted(
        actual.netting_set_lines,
        key=lambda line: (line.counterparty_id, line.netting_set_id),
    )
    expected_lines = sorted(
        expected["netting_set_lines"],
        key=lambda line: (line["counterparty_id"], line["netting_set_id"]),
    )
    assert len(actual_lines) == len(expected_lines)
    for actual_line, expected_line in zip(actual_lines, expected_lines, strict=True):
        assert actual_line.netting_set_id == expected_line["netting_set_id"]
        assert actual_line.counterparty_id == expected_line["counterparty_id"]
        assert actual_line.ead == pytest.approx(expected_line["ead"])
        assert actual_line.effective_maturity == pytest.approx(
            expected_line["effective_maturity"]
        )
        assert actual_line.discount_factor == pytest.approx(expected_line["discount_factor"])
        expected_risk_weight = expected_line.get("risk_weight", expected.get("risk_weight"))
        assert expected_risk_weight is not None, (
            f"risk_weight missing for netting set {actual_line.netting_set_id}"
        )
        assert actual_line.risk_weight == pytest.approx(expected_risk_weight)
        assert actual_line.alpha == pytest.approx(expected["alpha"])
        assert actual_line.standalone_capital == pytest.approx(
            expected_line["standalone_capital"]
        )

    actual_counterparties = sorted(
        actual.counterparty_capitals,
        key=lambda counterparty: counterparty.counterparty_id,
    )
    expected_counterparties = sorted(
        expected["counterparty_capitals"],
        key=lambda counterparty: counterparty["counterparty_id"],
    )
    assert len(actual_counterparties) == len(expected_counterparties)
    for actual_counterparty, expected_counterparty in zip(
        actual_counterparties,
        expected_counterparties,
        strict=True,
    ):
        assert (
            actual_counterparty.counterparty_id
            == expected_counterparty["counterparty_id"]
        )
        assert actual_counterparty.standalone_capital == pytest.approx(
            expected_counterparty["standalone_capital"]
        )
        assert sorted(actual_counterparty.netting_set_ids) == sorted(
            expected_counterparty["netting_set_ids"]
        )
