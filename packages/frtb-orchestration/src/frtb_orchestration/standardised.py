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

# Maps every known SA component profile_id to a jurisdiction family.
# Components from different families must never be composed into a single SA charge.
# Basel note: SBM uses "BASEL_MAR21", RRAO uses "BASEL_MAR23", and DRC would use
# "BASEL_MAR22" — three different MAR chapter labels, one Basel jurisdiction.
# See ADR 0022.
_SA_JURISDICTION_FAMILY: dict[str, str] = {
    "BASEL_MAR21": "BASEL",
    "BASEL_MAR22": "BASEL",
    "BASEL_MAR23": "BASEL",
    "US_NPR_2_0": "US_NPR",
    "EU_CRR3": "EU_CRR3",
}


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
        run_id=_required_text_attr(result, "run_id", component="RRAO"),
        calculation_date=_required_date_attr(result, "calculation_date", component="RRAO"),
        base_currency=_required_text_attr(result, "base_currency", component="RRAO"),
        profile_id=_required_text_attr(result, "profile_id", component="RRAO"),
        total_capital=_required_finite_number_attr(result, "total_rrao", component="RRAO"),
        profile_hash=_required_text_attr(result, "profile_hash", component="RRAO"),
        input_hash=_required_text_attr(result, "input_hash", component="RRAO"),
        line_count=_sequence_length_attr(result, "lines", component="RRAO"),
        excluded_line_count=_sequence_length_attr(result, "excluded_lines", component="RRAO"),
        subtotal_count=_sequence_length_attr(result, "subtotals", component="RRAO"),
        citations=_text_tuple_attr(result, "citations", component="RRAO"),
        warnings=_text_tuple_attr(result, "warnings", component="RRAO"),
    )


def recognise_drc_result(result: object) -> ComponentResultHandoff:
    """Return the orchestration handoff view for a public DRC result shape."""

    return ComponentResultHandoff(
        component=StandardisedComponent.DRC,
        package_name=_optional_text_attr(
            result, "package_name", component="DRC", default="frtb-drc"
        ),
        run_id=_required_text_attr(result, "run_id", component="DRC"),
        calculation_date=_required_date_attr(result, "calculation_date", component="DRC"),
        base_currency=_required_text_attr(result, "base_currency", component="DRC"),
        profile_id=_required_text_attr(result, "profile_id", component="DRC"),
        total_capital=_required_finite_number_attr(result, "total_drc", component="DRC"),
        profile_hash=_required_text_attr(result, "profile_hash", component="DRC"),
        input_hash=_required_text_attr(result, "input_hash", component="DRC"),
        line_count=_optional_count_or_sequence_attr(
            result,
            count_field="input_count",
            sequence_field="input_positions",
            component="DRC",
        ),
        excluded_line_count=_optional_count_or_sequence_attr(
            result,
            count_field="rejected_input_count",
            sequence_field="rejected_inputs",
            component="DRC",
        ),
        subtotal_count=_sequence_length_attr(result, "categories", component="DRC"),
        citations=_text_tuple_attr(result, "citations", component="DRC"),
        warnings=_text_tuple_attr(result, "warnings", component="DRC"),
    )


def recognise_sbm_result(result: object) -> ComponentResultHandoff:
    """Return the orchestration handoff view for the planned public SBM result shape."""

    return ComponentResultHandoff(
        component=StandardisedComponent.SBM,
        package_name=_optional_text_attr(
            result, "package_name", component="SBM", default="frtb-sbm"
        ),
        run_id=_required_text_attr(result, "run_id", component="SBM"),
        calculation_date=_required_date_attr(result, "calculation_date", component="SBM"),
        base_currency=_required_text_attr(result, "base_currency", component="SBM"),
        profile_id=_required_text_attr(result, "profile_id", component="SBM"),
        total_capital=_required_finite_number_attr(result, "total_sbm", component="SBM"),
        profile_hash=_required_text_attr(result, "profile_hash", component="SBM"),
        input_hash=_required_text_attr(result, "input_hash", component="SBM"),
        line_count=_optional_count_or_sequence_attr(
            result,
            count_field="sensitivity_count",
            sequence_field="sensitivities",
            component="SBM",
        ),
        excluded_line_count=_optional_count_or_sequence_attr(
            result,
            count_field="unsupported_count",
            sequence_field="unsupported_features",
            component="SBM",
        ),
        subtotal_count=_sequence_length_attr(result, "risk_class_results", component="SBM"),
        citations=_text_tuple_attr(result, "citations", component="SBM"),
        warnings=_text_tuple_attr(result, "warnings", component="SBM"),
    )


def compose_standardised_approach_capital(
    *,
    sbm_result: object | None = None,
    drc_result: object | None = None,
    rrao_result: object | None = None,
) -> NoReturn:
    """Fail explicitly until all SA component output contracts are available.

    Before checking for missing components, validates that all supplied component
    results share the same regulatory jurisdiction family (Basel, US-NPR, or
    EU-CRR3).  Mixing jurisdictions within a single SA charge is not a valid
    regulatory result.  See ADR 0022.
    """
    handoffs: list[ComponentResultHandoff] = []
    if rrao_result is not None:
        handoffs.append(recognise_rrao_result(rrao_result))
    if drc_result is not None:
        handoffs.append(recognise_drc_result(drc_result))
    if sbm_result is not None:
        handoffs.append(recognise_sbm_result(sbm_result))

    _assert_consistent_jurisdiction(handoffs)

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
        feature="standardised approach aggregation arithmetic",
    )


def _assert_consistent_jurisdiction(
    handoffs: Sequence[ComponentResultHandoff],
) -> None:
    """Raise OrchestrationInputError when supplied components span multiple jurisdictions."""
    families: dict[StandardisedComponent, tuple[str, str]] = {}
    for handoff in handoffs:
        family = _SA_JURISDICTION_FAMILY.get(handoff.profile_id)
        if family is None:
            raise OrchestrationInputError(
                f"{handoff.component.value} profile_id {handoff.profile_id!r} is not "
                "recognised as a known SA jurisdiction profile; add it to "
                "_SA_JURISDICTION_FAMILY in standardised.py",
                field="profile_id",
            )
        families[handoff.component] = (handoff.profile_id, family)

    unique_families = {family for _, family in families.values()}
    if len(unique_families) > 1:
        detail = ", ".join(
            f"{component.value}={profile_id!r}"
            for component, (profile_id, _) in sorted(families.items(), key=lambda item: item[0])
        )
        raise OrchestrationInputError(
            "SA components must share the same regulatory jurisdiction; "
            f"mixed profiles supplied: {detail}. "
            "All components must be from the same family (Basel, US_NPR, or EU_CRR3). "
            "See ADR 0022.",
            field="profile_id",
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


def _required_text_attr(result: object, field: str, *, component: str) -> str:
    value = _required_attr(result, field, component=component)
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(
            f"{component} result field {field} must be non-empty text",
            field=field,
        )
    return value


def _optional_text_attr(result: object, field: str, *, component: str, default: str) -> str:
    value = getattr(result, field, None)
    if value is None:
        return default
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(
            f"{component} result field {field} must be non-empty text",
            field=field,
        )
    return value


def _required_date_attr(result: object, field: str, *, component: str) -> date:
    value = _required_attr(result, field, component=component)
    if not isinstance(value, date):
        raise OrchestrationInputError(
            f"{component} result field {field} must be a date",
            field=field,
        )
    return value


def _required_finite_number_attr(result: object, field: str, *, component: str) -> float:
    value = _required_attr(result, field, component=component)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OrchestrationInputError(
            f"{component} result field {field} must be numeric",
            field=field,
        )
    number = float(value)
    if not math.isfinite(number):
        raise OrchestrationInputError(
            f"{component} result field {field} must be finite",
            field=field,
        )
    return number


def _sequence_length_attr(result: object, field: str, *, component: str) -> int:
    value = _required_attr(result, field, component=component)
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise OrchestrationInputError(
            f"{component} result field {field} must be a sequence",
            field=field,
        )
    return len(value)


def _optional_count_or_sequence_attr(
    result: object,
    *,
    count_field: str,
    sequence_field: str,
    component: str,
) -> int:
    value = getattr(result, count_field, None)
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise OrchestrationInputError(
                f"{component} result field {count_field} must be a non-negative integer",
                field=count_field,
            )
        return value
    return _sequence_length_attr(result, sequence_field, component=component)


def _text_tuple_attr(result: object, field: str, *, component: str) -> tuple[str, ...]:
    value = _required_attr(result, field, component=component)
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise OrchestrationInputError(
            f"{component} result field {field} must be a tuple of text values",
            field=field,
        )
    return value


def _required_attr(result: object, field: str, *, component: str) -> object:
    if not hasattr(result, field):
        raise OrchestrationInputError(
            f"{component} result is missing required field {field}",
            field=field,
        )
    return getattr(result, field)


__all__ = [
    "ComponentResultHandoff",
    "OrchestrationInputError",
    "StandardisedComponent",
    "compose_standardised_approach_capital",
    "recognise_drc_result",
    "recognise_rrao_result",
    "recognise_sbm_result",
]
