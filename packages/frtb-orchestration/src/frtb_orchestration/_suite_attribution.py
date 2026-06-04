"""Suite attribution label normalization and reconciliation helpers."""

from __future__ import annotations

from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_orchestration._validation import OrchestrationInputError

ATTRIBUTION_RECONCILIATION_TOLERANCE = 1e-6

TOP_LEVEL_ATTRIBUTION_COMPONENTS = ("frtb_ima", "frtb_sa", "frtb_cva")
DECOMPOSED_ATTRIBUTION_COMPONENTS = (
    "frtb_ima",
    "frtb_sbm",
    "frtb_drc",
    "frtb_rrao",
    "frtb_cva",
)

_COMPONENT_LABEL_ALIASES: dict[str, str] = {
    "ima": "frtb_ima",
    "frtb_ima": "frtb_ima",
    "frtb_ima_package": "frtb_ima",
    "frtb_ima_component": "frtb_ima",
    "sa": "frtb_sa",
    "standardised": "frtb_sa",
    "standardised_approach": "frtb_sa",
    "frtb_sa": "frtb_sa",
    "frtb_standardised": "frtb_sa",
    "sbm": "frtb_sbm",
    "frtb_sbm": "frtb_sbm",
    "drc": "frtb_drc",
    "frtb_drc": "frtb_drc",
    "rrao": "frtb_rrao",
    "frtb_rrao": "frtb_rrao",
    "cva": "frtb_cva",
    "frtb_cva": "frtb_cva",
}


def validate_component_bundles(
    component_bundles: tuple[ComponentContributionBundle, ...],
    component_capitals: dict[str, float],
) -> tuple[str, ...]:
    canonical_components: list[str] = []
    seen: set[str] = set()
    for bundle in component_bundles:
        component = canonical_component_label(bundle.component)
        if component in seen:
            raise OrchestrationInputError(
                f"duplicate contribution bundle for component {bundle.component!r}",
                field="component_bundles",
            )
        expected_total = component_capitals.get(component)
        if expected_total is None:
            raise OrchestrationInputError(
                f"component contribution bundle {bundle.component!r} is not recognised "
                "for suite attribution",
                field="component_bundles",
            )
        if not within_attribution_tolerance(bundle.component_total, expected_total):
            raise OrchestrationInputError(
                f"component contribution bundle {bundle.component!r} has component_total "
                f"{bundle.component_total:.6g}, expected {expected_total:.6g}",
                field="component_bundles",
            )
        canonical_components.append(component)
        seen.add(component)
    return tuple(canonical_components)


def require_supported_attribution_component_set(canonical_components: tuple[str, ...]) -> None:
    component_set = set(canonical_components)
    allowed_sets = (
        set(TOP_LEVEL_ATTRIBUTION_COMPONENTS),
        set(DECOMPOSED_ATTRIBUTION_COMPONENTS),
    )
    if component_set not in allowed_sets:
        expected = " or ".join(
            ", ".join(components)
            for components in (
                TOP_LEVEL_ATTRIBUTION_COMPONENTS,
                DECOMPOSED_ATTRIBUTION_COMPONENTS,
            )
        )
        actual = ", ".join(sorted(component_set)) or "<empty>"
        raise OrchestrationInputError(
            "component_bundles must contain exactly one complete suite attribution "
            f"component set; got {actual}, expected {expected}",
            field="component_bundles",
        )


def canonical_component_label(component: object, field: str = "component_bundles") -> str:
    if not isinstance(component, str) or not component:
        raise OrchestrationInputError(
            f"{field} component must be non-empty text",
            field=field,
        )
    normalised = component.strip().lower().replace("-", "_")
    canonical = _COMPONENT_LABEL_ALIASES.get(normalised)
    if canonical is None:
        raise OrchestrationInputError(
            f"{field} component {component!r} is not recognised",
            field=field,
        )
    return canonical


def canonical_standardised_component(component: str) -> str:
    return canonical_component_label(component, field="component_subtotals")


def within_attribution_tolerance(actual: float, expected: float) -> bool:
    tolerance = ATTRIBUTION_RECONCILIATION_TOLERANCE * max(abs(expected), 1.0)
    return abs(actual - expected) <= tolerance
