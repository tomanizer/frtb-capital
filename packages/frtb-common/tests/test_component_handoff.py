"""Tests for the shared standardised-component orchestration handoff contract."""

from __future__ import annotations

from datetime import date

import pytest
from frtb_common import (
    ComponentCapitalSummary,
    ComponentSummaryError,
    StandardisedComponent,
)


def _handoff(**overrides: object) -> ComponentCapitalSummary:
    fields: dict[str, object] = {
        "component": StandardisedComponent.SBM,
        "package_name": "frtb-sbm",
        "run_id": "run-001",
        "calculation_date": date(2026, 3, 31),
        "base_currency": "USD",
        "profile_id": "BASEL_MAR21",
        "total_capital": 100.0,
        "profile_hash": "profile-hash",
        "input_hash": "input-hash",
        "line_count": 3,
        "excluded_line_count": 1,
        "subtotal_count": 2,
        "citations": ("MAR21.4",),
        "warnings": (),
    }
    fields.update(overrides)
    return ComponentCapitalSummary(**fields)  # type: ignore[arg-type]


def test_valid_handoff_round_trips_fields() -> None:
    handoff = _handoff()

    assert handoff.component is StandardisedComponent.SBM
    assert handoff.total_capital == 100.0
    assert handoff.line_count == 3
    assert handoff.citations == ("MAR21.4",)


def test_component_must_be_enum() -> None:
    with pytest.raises(ComponentSummaryError, match="component must be a StandardisedComponent"):
        _handoff(component="SBM")


@pytest.mark.parametrize("field", ["package_name", "run_id", "base_currency", "profile_id"])
def test_required_text_fields_reject_empty(field: str) -> None:
    with pytest.raises(ComponentSummaryError, match=f"{field} must be non-empty text"):
        _handoff(**{field: ""})


def test_total_capital_must_be_finite() -> None:
    with pytest.raises(ComponentSummaryError, match="total_capital must be finite"):
        _handoff(total_capital=float("nan"))


def test_total_capital_rejects_bool() -> None:
    with pytest.raises(ComponentSummaryError, match="total_capital must be numeric"):
        _handoff(total_capital=True)


@pytest.mark.parametrize("field", ["line_count", "excluded_line_count", "subtotal_count"])
def test_counts_reject_negative(field: str) -> None:
    with pytest.raises(ComponentSummaryError, match=f"{field} must be a non-negative integer"):
        _handoff(**{field: -1})


def test_citations_must_be_text_tuple() -> None:
    with pytest.raises(ComponentSummaryError, match="citations must be a tuple of text values"):
        _handoff(citations=("ok", 5))
