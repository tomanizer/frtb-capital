"""Standardised Approach component composition.

Orchestration owns SA composition but never imports component packages. It
consumes the shared :class:`frtb_common.ComponentResultHandoff` shape that each
SA component projects via its own ``to_orchestration_handoff`` adapter. This
keeps orchestration decoupled from component-internal result fields and avoids
any sibling capital-package import.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NoReturn

from frtb_common import (
    ComponentResultHandoff,
    NotImplementedCapitalComponentError,
    StandardisedComponent,
)

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
    """Raised when a component handoff cannot be consumed by orchestration."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


def compose_standardised_approach_capital(
    *,
    sbm_handoff: ComponentResultHandoff | None = None,
    drc_handoff: ComponentResultHandoff | None = None,
    rrao_handoff: ComponentResultHandoff | None = None,
) -> NoReturn:
    """Fail explicitly until SA aggregation arithmetic (ADR 0018 M1a) lands.

    Each argument is the shared ``ComponentResultHandoff`` produced by the
    owning package's ``to_orchestration_handoff`` adapter. Before reporting
    missing components, this validates that every supplied handoff sits in its
    expected component slot and that all supplied components share one
    regulatory jurisdiction family (Basel, US-NPR, or EU-CRR3). Mixing
    jurisdictions within a single SA charge is not a valid regulatory result
    (ADR 0022).
    """

    _require_component(rrao_handoff, StandardisedComponent.RRAO, "rrao_handoff")
    _require_component(drc_handoff, StandardisedComponent.DRC, "drc_handoff")
    _require_component(sbm_handoff, StandardisedComponent.SBM, "sbm_handoff")

    handoffs = [
        handoff for handoff in (rrao_handoff, drc_handoff, sbm_handoff) if handoff is not None
    ]
    _assert_consistent_jurisdiction(handoffs)

    missing = _missing_standardised_components(
        sbm_handoff=sbm_handoff,
        drc_handoff=drc_handoff,
        rrao_handoff=rrao_handoff,
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


def _require_component(
    handoff: ComponentResultHandoff | None,
    expected: StandardisedComponent,
    param_name: str,
) -> None:
    if handoff is None:
        return
    if not isinstance(handoff, ComponentResultHandoff):
        raise OrchestrationInputError(
            f"{param_name} must be a frtb_common.ComponentResultHandoff",
            field=param_name,
        )
    if handoff.component is not expected:
        raise OrchestrationInputError(
            f"{param_name} carries a {handoff.component.value} handoff but "
            f"{expected.value} was expected",
            field=param_name,
        )


def _assert_consistent_jurisdiction(handoffs: Sequence[ComponentResultHandoff]) -> None:
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
    sbm_handoff: ComponentResultHandoff | None,
    drc_handoff: ComponentResultHandoff | None,
    rrao_handoff: ComponentResultHandoff | None,
) -> tuple[StandardisedComponent, ...]:
    missing: list[StandardisedComponent] = []
    if sbm_handoff is None:
        missing.append(StandardisedComponent.SBM)
    if drc_handoff is None:
        missing.append(StandardisedComponent.DRC)
    if rrao_handoff is None:
        missing.append(StandardisedComponent.RRAO)
    return tuple(missing)


__all__ = [
    "OrchestrationInputError",
    "compose_standardised_approach_capital",
]
