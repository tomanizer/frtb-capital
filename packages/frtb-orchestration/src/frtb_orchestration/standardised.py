"""Standardised Approach component handoff contracts.

The orchestration package owns SA composition, but this module intentionally
does not import component packages. It recognises stable public result shapes
structurally so component packages do not need to depend back on orchestration.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import NoReturn

from frtb_common import NotImplementedCapitalComponentError


class OrchestrationInputError(ValueError):
    """Raised when a component result cannot be consumed by orchestration."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


class StandardisedComponent(StrEnum):
    """Standardised Approach component result identifiers."""

    SBM = "SBM"
    DRC = "DRC"
    RRAO = "RRAO"


@dataclass(frozen=True)
class ComponentResultHandoff:
    """Component result summary consumed by future SA aggregation."""

    component: StandardisedComponent
    package_name: str
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    total_capital: float
    profile_hash: str
    input_hash: str
    line_count: int
    excluded_line_count: int
    subtotal_count: int
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def recognise_rrao_result(result: object) -> ComponentResultHandoff:
    """Return the orchestration handoff view for a public RRAO result shape."""

    return ComponentResultHandoff(
        component=StandardisedComponent.RRAO,
        package_name="frtb-rrao",
        run_id=_required_text_attr(result, "run_id"),
        calculation_date=_required_date_attr(result, "calculation_date"),
        base_currency=_required_text_attr(result, "base_currency"),
        profile_id=_required_text_attr(result, "profile_id"),
        total_capital=_required_finite_number_attr(result, "total_rrao"),
        profile_hash=_required_text_attr(result, "profile_hash"),
        input_hash=_required_text_attr(result, "input_hash"),
        line_count=_sequence_length_attr(result, "lines"),
        excluded_line_count=_sequence_length_attr(result, "excluded_lines"),
        subtotal_count=_sequence_length_attr(result, "subtotals"),
        citations=_text_tuple_attr(result, "citations"),
        warnings=_text_tuple_attr(result, "warnings"),
    )


def compose_standardised_approach_capital(
    *,
    sbm_result: object | None = None,
    drc_result: object | None = None,
    rrao_result: object | None = None,
) -> NoReturn:
    """Fail explicitly until all SA component output contracts are available."""

    if rrao_result is not None:
        recognise_rrao_result(rrao_result)

    missing = _missing_standardised_components(
        sbm_result=sbm_result,
        drc_result=drc_result,
        rrao_result=rrao_result,
    )
    if missing:
        raise NotImplementedCapitalComponentError(
            component="frtb-orchestration",
            feature=(
                "standardised approach aggregation; missing required component "
                f"outputs: {', '.join(component.value for component in missing)}"
            ),
        )

    raise NotImplementedCapitalComponentError(
        component="frtb-orchestration",
        feature=(
            "standardised approach aggregation until SBM and DRC result contracts are compatible"
        ),
    )


def _missing_standardised_components(
    *,
    sbm_result: object | None,
    drc_result: object | None,
    rrao_result: object | None,
) -> tuple[StandardisedComponent, ...]:
    missing: list[StandardisedComponent] = []
    if sbm_result is None:
        missing.append(StandardisedComponent.SBM)
    if drc_result is None:
        missing.append(StandardisedComponent.DRC)
    if rrao_result is None:
        missing.append(StandardisedComponent.RRAO)
    return tuple(missing)


def _required_text_attr(result: object, field: str) -> str:
    value = _required_attr(result, field)
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(
            f"RRAO result field {field} must be non-empty text",
            field=field,
        )
    return value


def _required_date_attr(result: object, field: str) -> date:
    value = _required_attr(result, field)
    if not isinstance(value, date):
        raise OrchestrationInputError(
            f"RRAO result field {field} must be a date",
            field=field,
        )
    return value


def _required_finite_number_attr(result: object, field: str) -> float:
    value = _required_attr(result, field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OrchestrationInputError(
            f"RRAO result field {field} must be numeric",
            field=field,
        )
    number = float(value)
    if not math.isfinite(number):
        raise OrchestrationInputError(
            f"RRAO result field {field} must be finite",
            field=field,
        )
    return number


def _sequence_length_attr(result: object, field: str) -> int:
    value = _required_attr(result, field)
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise OrchestrationInputError(
            f"RRAO result field {field} must be a sequence",
            field=field,
        )
    return len(value)


def _text_tuple_attr(result: object, field: str) -> tuple[str, ...]:
    value = _required_attr(result, field)
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise OrchestrationInputError(
            f"RRAO result field {field} must be a tuple of text values",
            field=field,
        )
    return value


def _required_attr(result: object, field: str) -> object:
    if not hasattr(result, field):
        raise OrchestrationInputError(
            f"RRAO result is missing required field {field}",
            field=field,
        )
    return getattr(result, field)


__all__ = [
    "ComponentResultHandoff",
    "OrchestrationInputError",
    "StandardisedComponent",
    "compose_standardised_approach_capital",
    "recognise_rrao_result",
]
