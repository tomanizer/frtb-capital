"""Scope-aware suite capital views over resolved component totals."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import require_non_empty_text as _require_non_empty_text
from frtb_orchestration._validation import (
    require_non_negative_finite_number as _require_non_negative_finite_number,
)


class ScopeViewStatus:
    """Stable status values for scope-aware capital views."""

    OK = "OK"
    NO_DATA = "NO_DATA"
    UNSUPPORTED = "UNSUPPORTED"


class BindingCapitalSide:
    """Stable binding-side labels for the output-floor comparison."""

    IMA = "IMA"
    SA_FLOOR = "SA_FLOOR"
    NO_DATA = "NO_DATA"


@dataclass(frozen=True)
class ScopeComponentCapital:
    """Capital total for one component within a resolved organisation scope."""

    component: str
    capital: float | None
    status: str = ScopeViewStatus.OK
    source_row_count: int = 0
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", _normalise_component(self.component))
        object.__setattr__(self, "status", _normalise_status(self.status))
        if self.capital is not None:
            object.__setattr__(
                self,
                "capital",
                _require_non_negative_finite_number(self.capital, "capital"),
            )
        if self.status == ScopeViewStatus.OK and self.capital is None:
            raise OrchestrationInputError("OK component capital must be present", field="capital")
        if self.status != ScopeViewStatus.OK and self.capital is not None:
            raise OrchestrationInputError(
                "non-OK component capital must be omitted",
                field="capital",
            )
        if self.source_row_count < 0:
            raise OrchestrationInputError(
                "source_row_count must be non-negative",
                field="source_row_count",
            )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic component view payload.

        Returns
        -------
        dict[str, object]
            JSON-compatible component capital payload.
        """

        return {
            "component": self.component,
            "capital": self.capital,
            "status": self.status,
            "source_row_count": self.source_row_count,
            "message": self.message,
        }


@dataclass(frozen=True)
class BindingCapitalResult:
    """Output-floor binding comparison for one resolved scope."""

    sa_total: float | None
    ima_total: float | None
    floor_multiplier: float
    floor_value: float | None
    binding_value: float | None
    binding_side: str
    status: str

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic binding-capital payload.

        Returns
        -------
        dict[str, object]
            JSON-compatible output-floor comparison payload.
        """

        return {
            "sa_total": self.sa_total,
            "ima_total": self.ima_total,
            "floor_multiplier": self.floor_multiplier,
            "floor_value": self.floor_value,
            "binding_value": self.binding_value,
            "binding_side": self.binding_side,
            "status": self.status,
        }


@dataclass(frozen=True)
class ScopeCapitalView:
    """Scope-aware capital summary for Navigator and downstream APIs."""

    run_id: str
    node_id: str
    node_label: str
    status: str
    total_capital: float | None
    sa_capital: float | None
    ima_capital: float | None
    cva_capital: float | None
    binding_capital: BindingCapitalResult
    components: tuple[ScopeComponentCapital, ...]

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _require_non_empty_text(self.node_label, "node_label")
        object.__setattr__(self, "status", _normalise_status(self.status))

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic scope-view payload.

        Returns
        -------
        dict[str, object]
            JSON-compatible scope capital view.
        """

        return {
            "run_id": self.run_id,
            "node_id": self.node_id,
            "node_label": self.node_label,
            "status": self.status,
            "total_capital": self.total_capital,
            "sa_capital": self.sa_capital,
            "ima_capital": self.ima_capital,
            "cva_capital": self.cva_capital,
            "binding_capital": self.binding_capital.as_dict(),
            "components": [component.as_dict() for component in self.components],
        }


_SA_COMPONENTS = ("SBM", "DRC", "RRAO")
_KNOWN_COMPONENTS = (*_SA_COMPONENTS, "IMA", "CVA")


def compose_scope_capital_view(
    *,
    run_id: str,
    node_id: str,
    node_label: str,
    component_capitals: Sequence[ScopeComponentCapital],
    floor_multiplier: float = 0.725,
) -> ScopeCapitalView:
    """Compose SA, IMA, CVA, and output-floor capital for one resolved scope.

    Parameters
    ----------
    run_id:
        Calculation run identifier.
    node_id:
        Result-store hierarchy node selected by the caller.
    node_label:
        Display label for the selected hierarchy node.
    component_capitals:
        Component totals already resolved to ``node_id`` by the result store or
        another scope-resolution layer.
    floor_multiplier:
        Output-floor multiplier applied to the SA total.

    Returns
    -------
    ScopeCapitalView
        Deterministic scope-aware capital summary.
    """

    _require_non_empty_text(run_id, "run_id")
    _require_non_empty_text(node_id, "node_id")
    _require_non_empty_text(node_label, "node_label")
    floor_multiplier = _require_non_negative_finite_number(
        floor_multiplier,
        "floor_multiplier",
    )
    if not isinstance(component_capitals, Sequence) or isinstance(component_capitals, str):
        raise OrchestrationInputError(
            "component_capitals must be a sequence of ScopeComponentCapital",
            field="component_capitals",
        )
    components = tuple(component_capitals)
    if not all(isinstance(component, ScopeComponentCapital) for component in components):
        raise OrchestrationInputError(
            "component_capitals must contain ScopeComponentCapital values",
            field="component_capitals",
        )
    components_by_name = _component_index(components)
    sa_capital = _compose_sa_capital(components_by_name)
    ima_capital = _ok_capital(components_by_name.get("IMA"))
    cva_capital = _ok_capital(components_by_name.get("CVA"))
    binding = _binding_result(sa_capital, ima_capital, floor_multiplier)
    total_capital = (
        binding.binding_value + (cva_capital or 0.0) if binding.binding_value is not None else None
    )
    return ScopeCapitalView(
        run_id=run_id,
        node_id=node_id,
        node_label=node_label,
        status=ScopeViewStatus.OK if total_capital is not None else ScopeViewStatus.NO_DATA,
        total_capital=total_capital,
        sa_capital=sa_capital,
        ima_capital=ima_capital,
        cva_capital=cva_capital,
        binding_capital=binding,
        components=tuple(sorted(components, key=lambda item: _component_sort_key(item.component))),
    )


def _component_index(
    components: tuple[ScopeComponentCapital, ...],
) -> dict[str, ScopeComponentCapital]:
    by_name: dict[str, ScopeComponentCapital] = {}
    for component in components:
        if component.component in by_name:
            raise OrchestrationInputError(
                f"duplicate scope component: {component.component}",
                field="component_capitals",
            )
        by_name[component.component] = component
    return by_name


def _compose_sa_capital(components: dict[str, ScopeComponentCapital]) -> float | None:
    sa_values = [_ok_capital(components.get(component)) for component in _SA_COMPONENTS]
    if any(value is None for value in sa_values):
        return None
    return math.fsum(value for value in sa_values if value is not None)


def _binding_result(
    sa_total: float | None,
    ima_total: float | None,
    floor_multiplier: float,
) -> BindingCapitalResult:
    if sa_total is None or ima_total is None:
        return BindingCapitalResult(
            sa_total=sa_total,
            ima_total=ima_total,
            floor_multiplier=floor_multiplier,
            floor_value=None,
            binding_value=None,
            binding_side=BindingCapitalSide.NO_DATA,
            status=ScopeViewStatus.NO_DATA,
        )
    floor_value = sa_total * floor_multiplier
    if floor_value > ima_total:
        binding_value = floor_value
        binding_side = BindingCapitalSide.SA_FLOOR
    else:
        binding_value = ima_total
        binding_side = BindingCapitalSide.IMA
    return BindingCapitalResult(
        sa_total=sa_total,
        ima_total=ima_total,
        floor_multiplier=floor_multiplier,
        floor_value=floor_value,
        binding_value=binding_value,
        binding_side=binding_side,
        status=ScopeViewStatus.OK,
    )


def _ok_capital(component: ScopeComponentCapital | None) -> float | None:
    if component is None or component.status != ScopeViewStatus.OK:
        return None
    return component.capital


def _normalise_component(component: str) -> str:
    _require_non_empty_text(component, "component")
    value = component.upper()
    if value == "STANDARDISED_APPROACH":
        value = "SA"
    if value not in _KNOWN_COMPONENTS and value != "SA":
        raise OrchestrationInputError(
            f"component must be one of: {', '.join((*_KNOWN_COMPONENTS, 'SA'))}",
            field="component",
        )
    return value


def _normalise_status(status: str) -> str:
    _require_non_empty_text(status, "status")
    value = status.upper()
    allowed = (ScopeViewStatus.OK, ScopeViewStatus.NO_DATA, ScopeViewStatus.UNSUPPORTED)
    if value not in allowed:
        raise OrchestrationInputError(
            f"status must be one of: {', '.join(allowed)}",
            field="status",
        )
    return value


def _component_sort_key(component: str) -> int:
    order = {name: index for index, name in enumerate((*_SA_COMPONENTS, "IMA", "CVA", "SA"))}
    return order[component]


__all__ = [
    "BindingCapitalResult",
    "BindingCapitalSide",
    "ScopeCapitalView",
    "ScopeComponentCapital",
    "ScopeViewStatus",
    "compose_scope_capital_view",
]
