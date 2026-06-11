"""
Portfolio scenario-selection alignment helpers for SBM aggregation results.

Regulatory traceability:
    Basel MAR21.7(2) — select the largest portfolio capital across scenarios.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from frtb_sbm.data_models import (
    BucketCapital,
    RiskClassCapital,
    SbmBranchMetadata,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
)
from frtb_sbm.kernel.aggregation import select_max_correlation_scenario
from frtb_sbm.validation import SbmInputError

_MAR21_SCENARIO_SELECTION_CITATION = ("basel_mar21_7_scenario_selection",)


def compute_portfolio_scenario_totals(
    risk_class_results: Sequence[RiskClassCapital],
) -> dict[SbmScenarioLabel, float]:
    """Sum risk-class scenario totals across supported measures per MAR21.7.
    Parameters
    ----------
    risk_class_results : Sequence[RiskClassCapital]
        See signature.

    Returns
    -------
    dict[SbmScenarioLabel, float]
    """

    if not risk_class_results:
        raise SbmInputError(
            "risk_class_results must not be empty",
            field="risk_class_results",
        )
    portfolio_totals: dict[SbmScenarioLabel, float] = {}
    for risk_class_result in risk_class_results:
        if risk_class_result.scenario_totals is None:
            raise SbmInputError(
                "risk-class capital must include scenario totals for portfolio selection",
                field="scenario_totals",
            )
        for scenario, total in risk_class_result.scenario_totals.items():
            portfolio_totals[scenario] = portfolio_totals.get(scenario, 0.0) + float(total)
    if not portfolio_totals:
        raise SbmInputError(
            "portfolio scenario totals must not be empty",
            field="portfolio_scenario_totals",
        )
    return portfolio_totals


def select_portfolio_correlation_scenario(
    risk_class_results: Sequence[RiskClassCapital],
    *,
    citation_ids: tuple[str, ...] = _MAR21_SCENARIO_SELECTION_CITATION,
) -> tuple[
    tuple[RiskClassCapital, ...],
    float,
    dict[SbmScenarioLabel, float],
    SbmScenarioLabel,
    SbmBranchMetadata,
]:
    """Apply MAR21.7 portfolio-level scenario selection across risk classes.

    Sums delta, vega, and curvature capital by scenario across present risk
    classes, selects the largest portfolio total, and aligns each risk-class
    result to that scenario for reconciliation.
    Parameters
    ----------
    risk_class_results : Sequence[RiskClassCapital]
        See signature.
    citation_ids : tuple[str, ...], optional
        See signature.

    Returns
    -------
    tuple[tuple[RiskClassCapital, ...], float, dict[SbmScenarioLabel, float],
        SbmScenarioLabel, SbmBranchMetadata]
        Aggregated capital result and branch metadata.
    """
    if not risk_class_results:
        raise SbmInputError(
            "risk_class_results must not be empty",
            field="risk_class_results",
        )

    portfolio_totals = compute_portfolio_scenario_totals(risk_class_results)
    selection = select_max_correlation_scenario(
        portfolio_totals,
        risk_class=SbmRiskClass.GIRR,
        branch_id="portfolio_scenario_selection",
        citation_ids=citation_ids,
    )
    aligned = tuple(
        align_risk_class_to_scenario(
            risk_class_result,
            selection.selected_scenario,
        )
        for risk_class_result in risk_class_results
    )
    return (
        aligned,
        selection.selected_capital,
        portfolio_totals,
        selection.selected_scenario,
        selection.branch_metadata,
    )


def align_risk_class_to_scenario(
    risk_class_result: RiskClassCapital,
    scenario: SbmScenarioLabel,
) -> RiskClassCapital:
    """Return a risk-class result whose selected buckets match ``scenario``.
    Parameters
    ----------
    risk_class_result : RiskClassCapital
        See signature.
    scenario : SbmScenarioLabel
        See signature.

    Returns
    -------
    RiskClassCapital
    """

    if risk_class_result.scenario_totals is None:
        raise SbmInputError(
            "risk-class capital must include scenario totals",
            field="scenario_totals",
        )
    if scenario not in risk_class_result.scenario_totals:
        raise SbmInputError(
            "risk-class scenario totals do not include requested scenario",
            field="selected_scenario",
        )
    if risk_class_result.selected_scenario is scenario:
        return risk_class_result

    selected_capital = float(risk_class_result.scenario_totals[scenario])
    detail = next(
        (item for item in risk_class_result.scenario_details if item.scenario is scenario),
        None,
    )
    if detail is None:
        raise SbmInputError(
            "risk-class scenario details must include requested scenario",
            field="scenario_details",
        )
    risk_measure = _risk_measure_for_alignment(risk_class_result)
    weighted_by_bucket = {
        bucket.bucket_id: bucket.weighted_sensitivities for bucket in risk_class_result.buckets
    }
    buckets = tuple(
        BucketCapital(
            bucket_id=intra.bucket_id,
            risk_class=risk_class_result.risk_class,
            risk_measure=risk_measure,
            kb=intra.kb,
            weighted_sensitivities=weighted_by_bucket.get(intra.bucket_id, ()),
            citation_ids=intra.citation_ids,
            sb=intra.sb,
            floor_applied=intra.floor_applied,
            scenario=scenario,
        )
        for intra in detail.intra_buckets
    )

    scenario_selection = risk_class_result.scenario_selection
    if scenario_selection is not None:
        scenario_selection = replace(
            scenario_selection,
            reason=(
                f"aligned to portfolio {scenario.value} scenario with capital {selected_capital}"
            ),
        )

    return replace(
        risk_class_result,
        selected_capital=selected_capital,
        selected_scenario=scenario,
        buckets=buckets,
        scenario_selection=scenario_selection,
    )


def _risk_measure_for_alignment(risk_class_result: RiskClassCapital) -> SbmRiskMeasure:
    if risk_class_result.risk_measure is not None:
        return risk_class_result.risk_measure
    if risk_class_result.buckets:
        return risk_class_result.buckets[0].risk_measure
    raise SbmInputError(
        "risk-class capital must include a risk measure for scenario alignment",
        field="risk_measure",
    )


__all__ = [
    "align_risk_class_to_scenario",
    "compute_portfolio_scenario_totals",
    "select_portfolio_correlation_scenario",
]
