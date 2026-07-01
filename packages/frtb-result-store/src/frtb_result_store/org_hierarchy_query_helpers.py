"""Internal helpers for organisation hierarchy query APIs."""

from __future__ import annotations

from collections.abc import Sequence

from frtb_result_store.model_enums import FrtbComponent, ResultStoreContractError
from frtb_result_store.org_hierarchy_model import OrgCapitalResultRow, component_value

UNSUPPORTED_FRAMEWORKS = frozenset({"RFET", "UPL", "SES", "NMRF"})


def component_filter(framework: str | None) -> tuple[tuple[FrtbComponent, ...], str]:
    """Return component filters or an unsupported-framework message.

    Parameters
    ----------
    framework:
        Optional FRTB framework/component filter supplied by a query caller.

    Returns
    -------
    tuple[tuple[FrtbComponent, ...], str]
        Component filters and an unsupported-framework message when the
        requested dataset is not represented by organisation capital rows.
    """

    if framework is None or framework == "":
        return (), ""
    normalized = framework.upper()
    if normalized in UNSUPPORTED_FRAMEWORKS:
        return (), f"framework is not available in organisation capital rows: {normalized}"
    try:
        return (FrtbComponent(normalized),), ""
    except ValueError as exc:
        allowed = ", ".join(
            sorted([component.value for component in FrtbComponent] + list(UNSUPPORTED_FRAMEWORKS))
        )
        raise ResultStoreContractError(
            f"framework must be one of: {allowed}",
            field="framework",
        ) from exc


def validate_measure(measure: str) -> None:
    """Reject measures not represented by organisation capital rows.

    Parameters
    ----------
    measure:
        Requested aggregate measure name.
    """

    if measure != "capital":
        raise ResultStoreContractError("measure must be one of: capital", field="measure")


def validate_page(limit: int, offset: int) -> None:
    """Reject invalid source-row page bounds.

    Parameters
    ----------
    limit:
        Maximum source rows to return.
    offset:
        Zero-based source row offset.
    """

    if limit < 1 or limit > 1000:
        raise ResultStoreContractError("limit must be between 1 and 1000", field="limit")
    if offset < 0:
        raise ResultStoreContractError("offset must be non-negative", field="offset")


def single_currency(rows: Sequence[OrgCapitalResultRow]) -> str:
    """Return the one source-row currency or fail closed.

    Parameters
    ----------
    rows:
        Source rows contributing to one aggregate.

    Returns
    -------
    str
        Single currency shared by all contributing source rows.
    """

    currencies = sorted({row.currency for row in rows})
    if len(currencies) != 1:
        raise ResultStoreContractError(
            "org aggregate rows must not mix currencies",
            field="currency",
        )
    return currencies[0]


def component_breakdown(rows: Sequence[OrgCapitalResultRow]) -> dict[str, float]:
    """Return deterministic component capital totals.

    Parameters
    ----------
    rows:
        Source rows contributing to one aggregate.

    Returns
    -------
    dict[str, float]
        Capital totals keyed by component value.
    """

    breakdown: dict[str, float] = {}
    for row in rows:
        component = component_value(row.component)
        breakdown[component] = breakdown.get(component, 0.0) + row.capital
    return dict(sorted(breakdown.items()))


__all__ = [
    "component_breakdown",
    "component_filter",
    "single_currency",
    "validate_measure",
    "validate_page",
]
