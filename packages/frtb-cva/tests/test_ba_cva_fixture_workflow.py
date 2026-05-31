from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from frtb_cva import calculate_cva_capital

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ba_cva_reduced_v1"
sys.path.insert(0, str(FIXTURE_DIR))
from loader import load_fixture_cases, load_fixture_context, load_invalid_cases  # noqa: E402


def test_fixture_cases_produce_deterministic_capital() -> None:
    context = load_fixture_context()
    totals: list[float] = []
    for case_id, counterparties, netting_sets in load_fixture_cases():
        result = calculate_cva_capital(context, counterparties, netting_sets)
        assert result.total_cva_capital > 0.0, case_id
        totals.append(result.total_cva_capital)
    assert len(set(totals)) == len(totals)


def test_invalid_fixture_cases_fail_before_capital() -> None:
    context = load_fixture_context()
    for case_id, expected_match, counterparties, netting_sets in load_invalid_cases():
        with pytest.raises(Exception, match=expected_match):
            calculate_cva_capital(context, counterparties, netting_sets)


def test_package_does_not_import_sibling_capital_packages() -> None:
    forbidden_prefixes = ("frtb_rrao", "frtb_sbm", "frtb_drc", "frtb_ima", "frtb_orchestration")
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
    ):
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding="utf-8")
        for prefix in forbidden_prefixes:
            assert prefix not in source
    assert package.__name__ == "frtb_cva"
