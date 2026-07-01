"""Persisted reporting mart generation for the Parquet result store."""

from __future__ import annotations

from collections.abc import Sequence

from frtb_result_store.mart_attribution_rows import (
    _residual_attribution_rows,
    _top_contributor_rows,
    _unsupported_attribution_rows,
)
from frtb_result_store.mart_capital_tree_rows import (
    _capital_tree_rows,
)
from frtb_result_store.mart_component_breakdown_rows import (
    _component_breakdown_rows,
)
from frtb_result_store.mart_component_rows import (
    _cva_counterparty_contributor_rows,
    _drc_issuer_contributor_rows,
    _ima_desk_dashboard_rows,
    _rrao_exposure_summary_rows,
    _sbm_bucket_ladder_rows,
)
from frtb_result_store.mart_desk_eligibility_rows import (
    _desk_eligibility_mart_rows,
)
from frtb_result_store.mart_movement_rows import (
    _movement_summary_rows,
)
from frtb_result_store.mart_rfet_nmrf_ses_rows import (
    _rfet_nmrf_ses_evidence_mart_rows,
)
from frtb_result_store.mart_row_codecs import (
    capital_summary_from_row as _capital_summary_from_row,
)
from frtb_result_store.mart_row_codecs import (
    capital_tree_mart_from_row as _capital_tree_mart_from_row,
)
from frtb_result_store.mart_row_codecs import (
    component_breakdown_from_row as _component_breakdown_from_row,
)
from frtb_result_store.mart_row_codecs import (
    movement_summary_from_row as _movement_summary_from_row,
)
from frtb_result_store.mart_summary_rows import (
    capital_summary_row,
    regime_comparison_row,
)
from frtb_result_store.model import (
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    MovementSummaryRow,
    ResultBundle,
    RunStatus,
)

__all__ = [
    "capital_summary_from_row",
    "capital_tree_mart_from_row",
    "component_breakdown_from_row",
    "mart_rows_for_bundle",
    "movement_summary_from_row",
]


def mart_rows_for_bundle(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, list[dict[str, object]]]:
    """Project one result bundle into every persisted reporting mart.

    Parameters
    ----------
    bundle:
        Validated run result bundle to serialize.
    lifecycle_status:
        Current append-only lifecycle state to stamp into summary-level marts.

    Returns
    -------
    dict[str, list[dict[str, object]]]
        Mapping from mart name to storage-ready row dictionaries.
    """

    return {
        "capital_summary": [capital_summary_row(bundle, lifecycle_status=lifecycle_status)],
        "capital_tree": _capital_tree_rows(bundle),
        "top_contributors": _top_contributor_rows(bundle),
        "residual_attribution": _residual_attribution_rows(bundle),
        "unsupported_attribution": _unsupported_attribution_rows(bundle),
        "movement_summary": _movement_summary_rows(bundle),
        "regime_comparison": [regime_comparison_row(bundle, lifecycle_status=lifecycle_status)],
        "component_breakdown": _component_breakdown_rows(bundle),
        "ima_desk_dashboard": _ima_desk_dashboard_rows(bundle),
        "sbm_bucket_ladder": _sbm_bucket_ladder_rows(bundle),
        "drc_issuer_contributors": _drc_issuer_contributor_rows(bundle),
        "cva_counterparty_contributors": _cva_counterparty_contributor_rows(bundle),
        "rrao_exposure_summary": _rrao_exposure_summary_rows(bundle),
        "rfet_nmrf_ses_evidence": _rfet_nmrf_ses_evidence_mart_rows(bundle),
        "desk_eligibility": _desk_eligibility_mart_rows(bundle),
    }


def capital_summary_from_row(row: Sequence[object]) -> CapitalSummaryRow:
    """Deserialize one persisted capital-summary mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``capital_summary`` mart.

    Returns
    -------
    CapitalSummaryRow
        Typed capital-summary projection row.
    """

    return _capital_summary_from_row(row)


def capital_tree_mart_from_row(row: Sequence[object]) -> CapitalTreeMartRow:
    """Deserialize one persisted capital-tree mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``capital_tree`` mart.

    Returns
    -------
    CapitalTreeMartRow
        Typed flattened capital-tree projection row.
    """

    return _capital_tree_mart_from_row(row)


def component_breakdown_from_row(row: Sequence[object]) -> ComponentBreakdownRow:
    """Deserialize one persisted component-breakdown mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``component_breakdown`` mart.

    Returns
    -------
    ComponentBreakdownRow
        Typed component-level capital total projection row.
    """

    return _component_breakdown_from_row(row)


def movement_summary_from_row(row: Sequence[object]) -> MovementSummaryRow:
    """Deserialize one persisted movement-summary mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``movement_summary`` mart.

    Returns
    -------
    MovementSummaryRow
        Typed capital movement projection row.
    """

    return _movement_summary_from_row(row)
