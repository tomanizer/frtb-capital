"""Standardised Approach component validation and normalization helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from frtb_common import (
    ComponentCapitalSummary,
    NotImplementedCapitalComponentError,
    StandardisedComponent,
)

from frtb_orchestration._standardised_models import (
    _IMA_ELIGIBLE,
    _SA_FALLBACK,
    _SA_JURISDICTION_FAMILY,
    StandardisedFallbackRoute,
)
from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import require_non_empty_text as _require_non_empty_text


def standardised_jurisdiction_family(profile_id: str) -> str:
    """Return the ADR 0022 SA jurisdiction family for a public profile id.

    Parameters
    ----------
    profile_id : str
        Profile id.

    Returns
    -------
    str
        Result of the operation.
    """

    _require_non_empty_text(profile_id, "profile_id")
    family = _SA_JURISDICTION_FAMILY.get(profile_id)
    if family is None:
        raise OrchestrationInputError(
            f"profile_id {profile_id!r} is not recognised as a known SA jurisdiction profile",
            field="profile_id",
        )
    return family


def resolve_required_standardised_summaries(
    *,
    sbm_summary: ComponentCapitalSummary | None,
    drc_summary: ComponentCapitalSummary | None,
    rrao_summary: ComponentCapitalSummary | None,
) -> tuple[ComponentCapitalSummary, ComponentCapitalSummary, ComponentCapitalSummary]:
    """Validate and return SBM, DRC, and RRAO summaries in aggregation order.

    Parameters
    ----------
    sbm_summary : ComponentCapitalSummary | None
        SBM component summary.
    drc_summary : ComponentCapitalSummary | None
        DRC component summary.
    rrao_summary : ComponentCapitalSummary | None
        RRAO component summary.

    Returns
    -------
    tuple[ComponentCapitalSummary, ComponentCapitalSummary, ComponentCapitalSummary]
        Validated summaries in SBM, DRC, RRAO aggregation order.
    """

    _require_component(rrao_summary, StandardisedComponent.RRAO, "rrao_summary")
    _require_component(drc_summary, StandardisedComponent.DRC, "drc_summary")
    _require_component(sbm_summary, StandardisedComponent.SBM, "sbm_summary")

    summaries = [
        summary for summary in (rrao_summary, drc_summary, sbm_summary) if summary is not None
    ]
    _assert_consistent_jurisdiction(summaries)
    missing = _missing_standardised_components(
        sbm_summary=sbm_summary,
        drc_summary=drc_summary,
        rrao_summary=rrao_summary,
    )
    if missing:
        raise NotImplementedCapitalComponentError(
            component="frtb-orchestration",
            feature=(
                "standardised approach aggregation; missing required component "
                f"outputs: {', '.join(component.value for component in missing)}"
            ),
        )

    assert sbm_summary is not None
    assert drc_summary is not None
    assert rrao_summary is not None
    required_summaries = (sbm_summary, drc_summary, rrao_summary)
    _assert_consistent_run_context(required_summaries)
    for summary in required_summaries:
        _assert_non_negative_component_capital(summary)
    return required_summaries


def normalise_result_run_id(
    run_id: str | None,
    summaries: Sequence[ComponentCapitalSummary],
) -> str:
    """Return a caller-supplied or deterministic SA run id.

    Parameters
    ----------
    run_id : str | None
        Optional caller-supplied run identifier.
    summaries : Sequence[ComponentCapitalSummary]
        Validated component summaries in aggregation order.

    Returns
    -------
    str
        Effective SA result run identifier.
    """

    if run_id is None:
        return _default_sa_run_id(summaries)
    _require_non_empty_text(run_id, "run_id")
    return run_id


def normalise_fallback_routes(
    ima_desk_eligibility: Mapping[str, object] | None,
) -> tuple[StandardisedFallbackRoute, ...]:
    """Return deterministic SA fallback route records from IMA desk eligibility.

    Parameters
    ----------
    ima_desk_eligibility : Mapping[str, object] | None
        Optional mapping of desk id to IMA eligibility status.

    Returns
    -------
    tuple[StandardisedFallbackRoute, ...]
        Deterministically ordered SA fallback routes.
    """

    if ima_desk_eligibility is None:
        return ()
    if not isinstance(ima_desk_eligibility, Mapping):
        raise OrchestrationInputError(
            "ima_desk_eligibility must be a mapping of desk_id to eligibility status",
            field="ima_desk_eligibility",
        )

    routes: list[StandardisedFallbackRoute] = []
    entries: list[tuple[str, object]] = []
    for desk_id, raw_status in ima_desk_eligibility.items():
        if not isinstance(desk_id, str) or not desk_id:
            raise OrchestrationInputError(
                "ima_desk_eligibility keys must be non-empty desk_id strings",
                field="ima_desk_eligibility",
            )
        entries.append((desk_id, raw_status))

    for desk_id, raw_status in sorted(entries, key=lambda item: item[0]):
        status = _eligibility_status_value(raw_status)
        if status == _SA_FALLBACK:
            routes.append(StandardisedFallbackRoute(desk_id=desk_id))
        elif status != _IMA_ELIGIBLE:
            raise OrchestrationInputError(
                f"desk {desk_id!r} has unsupported eligibility status {status!r}; "
                f"expected {_IMA_ELIGIBLE!r} or {_SA_FALLBACK!r}",
                field="ima_desk_eligibility",
            )
    return tuple(routes)


def unique_texts(values: Iterable[str]) -> tuple[str, ...]:
    """Return values in first-seen order with duplicates removed.

    Parameters
    ----------
    values : Iterable[str]
        Text values to de-duplicate.

    Returns
    -------
    tuple[str, ...]
        Unique text values in first-seen order.
    """

    return tuple(dict.fromkeys(values))


def _require_component(
    summary: ComponentCapitalSummary | None,
    expected: StandardisedComponent,
    param_name: str,
) -> None:
    if summary is None:
        return
    if not isinstance(summary, ComponentCapitalSummary):
        raise OrchestrationInputError(
            f"{param_name} must be a frtb_common.ComponentCapitalSummary",
            field=param_name,
        )
    if summary.component is not expected:
        raise OrchestrationInputError(
            f"{param_name} carries a {summary.component.value} summary but "
            f"{expected.value} was expected",
            field=param_name,
        )


def _assert_consistent_jurisdiction(summaries: Sequence[ComponentCapitalSummary]) -> None:
    """Raise OrchestrationInputError when supplied components span multiple jurisdictions."""

    families: dict[StandardisedComponent, tuple[str, str]] = {}
    for summary in summaries:
        family = _jurisdiction_family(summary)
        families[summary.component] = (summary.profile_id, family)

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
    sbm_summary: ComponentCapitalSummary | None,
    drc_summary: ComponentCapitalSummary | None,
    rrao_summary: ComponentCapitalSummary | None,
) -> tuple[StandardisedComponent, ...]:
    missing: list[StandardisedComponent] = []
    if sbm_summary is None:
        missing.append(StandardisedComponent.SBM)
    if drc_summary is None:
        missing.append(StandardisedComponent.DRC)
    if rrao_summary is None:
        missing.append(StandardisedComponent.RRAO)
    return tuple(missing)


def _jurisdiction_family(summary: ComponentCapitalSummary) -> str:
    try:
        return standardised_jurisdiction_family(summary.profile_id)
    except OrchestrationInputError as exc:
        raise OrchestrationInputError(
            f"{summary.component.value} profile_id {summary.profile_id!r} is not "
            "recognised as a known SA jurisdiction profile",
            field="profile_id",
        ) from exc


def _assert_consistent_run_context(summaries: Sequence[ComponentCapitalSummary]) -> None:
    calculation_dates = {summary.calculation_date for summary in summaries}
    if len(calculation_dates) > 1:
        detail = _context_detail(summaries, "calculation_date")
        raise OrchestrationInputError(
            f"SA components must share the same calculation_date; mixed dates supplied: {detail}",
            field="calculation_date",
        )

    base_currencies = {summary.base_currency for summary in summaries}
    if len(base_currencies) > 1:
        detail = _context_detail(summaries, "base_currency")
        raise OrchestrationInputError(
            "SA components must share the same base_currency before aggregation; "
            f"mixed currencies supplied: {detail}",
            field="base_currency",
        )


def _assert_non_negative_component_capital(summary: ComponentCapitalSummary) -> None:
    if summary.total_capital < 0.0:
        raise OrchestrationInputError(
            f"{summary.component.value} total_capital must be non-negative for SA composition",
            field="total_capital",
        )


def _context_detail(summaries: Sequence[ComponentCapitalSummary], field: str) -> str:
    return ", ".join(
        f"{summary.component.value}={getattr(summary, field)!r}"
        for summary in sorted(summaries, key=lambda item: item.component)
    )


def _default_sa_run_id(summaries: Sequence[ComponentCapitalSummary]) -> str:
    return "sa:" + ":".join(summary.run_id for summary in summaries)


def _eligibility_status_value(raw_status: object) -> str:
    value = getattr(raw_status, "value", raw_status)
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(
            "IMA desk eligibility status values must be non-empty strings or string enums",
            field="ima_desk_eligibility",
        )
    return value


__all__ = [
    "normalise_fallback_routes",
    "normalise_result_run_id",
    "resolve_required_standardised_summaries",
    "standardised_jurisdiction_family",
    "unique_texts",
]
