"""Row deserializers for persisted result-store reporting marts."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from frtb_result_store._row_codecs import (
    float_value as _float_value,
)
from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store.model import (
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    MovementSummaryRow,
)

__all__ = [
    "capital_summary_from_row",
    "capital_tree_mart_from_row",
    "component_breakdown_from_row",
    "movement_summary_from_row",
]


def capital_summary_from_row(row: Sequence[object]) -> CapitalSummaryRow:
    """Deserialize one persisted capital-summary mart row.

    Parameters
    ----------
    row
        Storage-order field sequence read from the ``capital_summary`` mart.

    Returns
    -------
    CapitalSummaryRow
        Typed mart projection row with storage text and numeric fields coerced.
    """

    return CapitalSummaryRow(
        run_id=str(row[0]),
        as_of_date=_date_from_storage(row[1]),
        regime_id=str(row[2]),
        base_currency=str(row[3]),
        lifecycle_status=str(row[4]),
        suggested_status=_optional_text(row[5]),
        total_capital=_float_value(row[6]),
        currency=str(row[7]),
        node_count=_int_value(row[8]),
        measure_count=_int_value(row[9]),
        component_count=_int_value(row[10]),
    )


def capital_tree_mart_from_row(row: Sequence[object]) -> CapitalTreeMartRow:
    """Deserialize one persisted capital-tree mart row.

    Parameters
    ----------
    row
        Storage-order field sequence read from the ``capital_tree`` mart.

    Returns
    -------
    CapitalTreeMartRow
        Typed tree projection row with optional identifiers and metadata decoded.
    """

    return CapitalTreeMartRow(
        run_id=str(row[0]),
        node_id=str(row[1]),
        parent_node_id=_optional_text(row[2]),
        depth=_int_value(row[3]),
        node_type=str(row[4]),
        component=str(row[5]),
        label=str(row[6]),
        desk_id=_optional_text(row[7]),
        portfolio_id=_optional_text(row[8]),
        book_id=_optional_text(row[9]),
        risk_class=_optional_text(row[10]),
        bucket=_optional_text(row[11]),
        issuer_id=_optional_text(row[12]),
        counterparty_id=_optional_text(row[13]),
        calculation_branch=_optional_text(row[14]),
        regulatory_rule_id=_optional_text(row[15]),
        sort_key=_int_value(row[16]),
        metadata=_json_mapping(row[17]),
    )


def component_breakdown_from_row(row: Sequence[object]) -> ComponentBreakdownRow:
    """Deserialize one persisted component-breakdown mart row.

    Parameters
    ----------
    row
        Storage-order field sequence read from the ``component_breakdown`` mart.

    Returns
    -------
    ComponentBreakdownRow
        Typed component projection row with capital amount and counts coerced.
    """

    return ComponentBreakdownRow(
        run_id=str(row[0]),
        component=str(row[1]),
        amount=_float_value(row[2]),
        currency=str(row[3]),
        node_count=_int_value(row[4]),
        measure_count=_int_value(row[5]),
    )


def movement_summary_from_row(row: Sequence[object]) -> MovementSummaryRow:
    """Deserialize one persisted movement-summary mart row.

    Parameters
    ----------
    row
        Storage-order field sequence read from the ``movement_summary`` mart.

    Returns
    -------
    MovementSummaryRow
        Typed movement projection row with numeric amounts and optional refs coerced.
    """

    return MovementSummaryRow(
        run_id=str(row[0]),
        baseline_run_id=str(row[1]),
        movement_id=str(row[2]),
        node_id=str(row[3]),
        movement_type=str(row[4]),
        from_amount=_float_value(row[5]),
        to_amount=_float_value(row[6]),
        delta_amount=_float_value(row[7]),
        base_currency=str(row[8]),
        driver_type=str(row[9]),
        driver_id=str(row[10]),
        attribution_method=_optional_text(row[11]),
        artifact_id=_optional_text(row[12]),
    )


def _date_from_storage(value: object) -> date:
    return date.fromisoformat(str(value))
