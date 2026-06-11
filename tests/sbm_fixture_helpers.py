"""Shared test-only helpers for SBM fixture loaders."""

from __future__ import annotations

from datetime import date
from typing import Any

from frtb_sbm import SbmCalculationContext


def load_sbm_fixture_context(payload: dict[str, Any]) -> SbmCalculationContext:
    if "context" not in payload:
        raise ValueError("Missing 'context' key in payload")
    context = payload["context"]
    for key in (
        "run_id",
        "calculation_date",
        "base_currency",
        "reporting_currency",
        "profile_id",
    ):
        if key not in context:
            raise ValueError(f"Missing '{key}' key in context payload")

    return SbmCalculationContext(
        run_id=str(context["run_id"]),
        calculation_date=date.fromisoformat(str(context["calculation_date"])),
        base_currency=str(context["base_currency"]),
        reporting_currency=str(context["reporting_currency"]),
        profile_id=str(context["profile_id"]),
    )
