"""Suite attribution aggregation and report builders."""

from __future__ import annotations

import math

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_orchestration._suite_attribution import (
    DECOMPOSED_ATTRIBUTION_COMPONENTS as _DECOMPOSED_ATTRIBUTION_COMPONENTS,
)
from frtb_orchestration._suite_attribution import (
    TOP_LEVEL_ATTRIBUTION_COMPONENTS as _TOP_LEVEL_ATTRIBUTION_COMPONENTS,
)
from frtb_orchestration._suite_attribution import (
    canonical_component_label as _canonical_component_label,
)
from frtb_orchestration._suite_attribution import (
    canonical_standardised_component as _canonical_standardised_component,
)
from frtb_orchestration._suite_attribution import (
    require_supported_attribution_component_set as _require_supported_attribution_component_set,
)
from frtb_orchestration._suite_attribution import (
    validate_component_bundles as _validate_component_bundles,
)
from frtb_orchestration._suite_attribution import (
    within_attribution_tolerance as _within_attribution_tolerance,
)
from frtb_orchestration._suite_attribution_models import (
    SuiteAttributionComponentReport,
    SuiteAttributionReport,
    SuiteAttributionResult,
    SuiteCapitalResult,
)
from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import (
    require_non_negative_finite_number as _require_non_negative_finite_number,
)
from frtb_orchestration._validation import require_tuple_of as _require_tuple_of


def aggregate_suite_attribution(
    *,
    suite_result: SuiteCapitalResult,
    component_bundles: tuple[ComponentContributionBundle, ...],
    suite_total_capital: float | None = None,
) -> SuiteAttributionResult:
    """Validate and aggregate component contribution bundles at suite level.

    Incoming component bundles and their contained ``CapitalContribution``
    records are preserved unchanged. The returned suite residual explicitly
    reconciles bundle totals to the top-of-house suite capital.
    Parameters
    ----------
    suite_result : SuiteCapitalResult
        Suite result.
    component_bundles : tuple[ComponentContributionBundle, ...]
        Component bundles.
    suite_total_capital : float | None, optional
        Suite total capital.

    Returns
    -------
    SuiteAttributionResult
        Result of the operation.
    """

    if not isinstance(suite_result, SuiteCapitalResult):
        raise OrchestrationInputError(
            "suite_result must be a SuiteCapitalResult", field="suite_result"
        )
    _require_tuple_of(component_bundles, ComponentContributionBundle, "component_bundles")
    if suite_total_capital is None:
        effective_suite_total = suite_result.total_capital
    else:
        effective_suite_total = _require_non_negative_finite_number(
            suite_total_capital, "suite_total_capital"
        )
    component_capitals = _expected_component_capitals(suite_result)
    canonical_components = _validate_component_bundles(component_bundles, component_capitals)
    _require_supported_attribution_component_set(canonical_components)

    component_total = math.fsum(bundle.component_total for bundle in component_bundles)
    residual = effective_suite_total - component_total
    residual_status = (
        ReconciliationStatus.RECONCILED
        if _within_attribution_tolerance(residual, 0.0)
        else ReconciliationStatus.PARTIAL_RESIDUAL
    )
    residual_reason = (
        "suite-level residual reconciles component contribution bundles to "
        "top-of-house capital; non-zero residuals represent explicitly "
        "unallocated cross-component interactions"
    )
    if residual_status == ReconciliationStatus.RECONCILED:
        residual_reason = (
            "suite-level residual record retained for audit; component "
            "contribution bundles reconcile exactly to top-of-house capital"
        )

    return SuiteAttributionResult(
        run_id=suite_result.run_id,
        suite_total_capital=effective_suite_total,
        component_bundles=component_bundles,
        suite_residual=CapitalContribution(
            contribution_id=f"{suite_result.run_id}:suite-residual",
            source_id=suite_result.run_id,
            source_level="suite",
            bucket_key=None,
            category="SUITE_RESIDUAL",
            base_amount=effective_suite_total,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.RESIDUAL,
            residual=residual,
            reason=residual_reason,
            citations=("ADR 0038",),
            reconciliation_status=residual_status,
        ),
    )


def build_suite_attribution_report(
    *,
    suite_result: SuiteCapitalResult,
    component_bundles: tuple[ComponentContributionBundle, ...],
    suite_total_capital: float | None = None,
) -> SuiteAttributionReport:
    """Build a deterministic client-facing suite attribution explain report.

    The builder delegates validation and suite-residual construction to
    :func:`aggregate_suite_attribution`. Component ``CapitalContribution``
    records are exposed unchanged, while component sections are ordered to the
    supported top-level or decomposed suite component set for stable notebook
    and JSON output.
    Parameters
    ----------
    suite_result : SuiteCapitalResult
        Suite result.
    component_bundles : tuple[ComponentContributionBundle, ...]
        Component bundles.
    suite_total_capital : float | None, optional
        Suite total capital.

    Returns
    -------
    SuiteAttributionReport
        Result of the operation.
    """

    attribution = aggregate_suite_attribution(
        suite_result=suite_result,
        component_bundles=component_bundles,
        suite_total_capital=suite_total_capital,
    )
    component_set = _canonical_component_set(attribution.component_bundles)
    bundle_by_component = {
        _canonical_component_label(bundle.component): bundle
        for bundle in attribution.component_bundles
    }
    components = tuple(
        SuiteAttributionComponentReport(
            component=component,
            component_total=bundle_by_component[component].component_total,
            component_input_hash=bundle_by_component[component].component_input_hash,
            component_profile_hash=bundle_by_component[component].component_profile_hash,
            contributions=bundle_by_component[component].contributions,
        )
        for component in component_set
    )
    return SuiteAttributionReport(
        run_id=attribution.run_id,
        suite_total_capital=attribution.suite_total_capital,
        component_set=component_set,
        components=components,
        suite_residual=attribution.suite_residual,
        reconciliation_status=ReconciliationStatus(
            attribution.suite_residual.reconciliation_status
        ),
        residual_reason=attribution.suite_residual.reason,
    )


def _expected_component_capitals(result: SuiteCapitalResult) -> dict[str, float]:
    component_capitals = {
        "frtb_ima": result.ima_capital,
        "frtb_sa": result.sa_capital,
        "frtb_cva": result.cva_capital,
    }
    for subtotal in result.sa_result.component_subtotals:
        component_capitals[_canonical_standardised_component(subtotal.component.value)] = (
            subtotal.total_capital
        )
    return component_capitals


def _canonical_component_set(
    component_bundles: tuple[ComponentContributionBundle, ...],
) -> tuple[str, ...]:
    canonical_components = {
        _canonical_component_label(bundle.component) for bundle in component_bundles
    }
    if canonical_components == set(_TOP_LEVEL_ATTRIBUTION_COMPONENTS):
        return _TOP_LEVEL_ATTRIBUTION_COMPONENTS
    if canonical_components == set(_DECOMPOSED_ATTRIBUTION_COMPONENTS):
        return _DECOMPOSED_ATTRIBUTION_COMPONENTS
    _require_supported_attribution_component_set(tuple(sorted(canonical_components)))
    raise AssertionError("unreachable")


__all__ = [
    "aggregate_suite_attribution",
    "build_suite_attribution_report",
]
