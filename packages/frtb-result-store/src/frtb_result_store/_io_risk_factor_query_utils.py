"""Private helpers for risk-factor metadata drilldown queries."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

from frtb_result_store.model import (
    FrtbComponent,
    ResultStoreContractError,
    RiskFactorMetadataRecord,
)
from frtb_result_store.store_schemas import _dict_rows

_MAX_RISK_FACTOR_PAGE_SIZE = 1000
_T = TypeVar("_T")


def _validate_page_window(limit: int, offset: int) -> tuple[int, int]:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ResultStoreContractError("limit must be an integer", field="limit")
    if not isinstance(offset, int) or isinstance(offset, bool):
        raise ResultStoreContractError("offset must be an integer", field="offset")
    if limit < 1 or limit > _MAX_RISK_FACTOR_PAGE_SIZE:
        raise ResultStoreContractError(
            f"limit must be between 1 and {_MAX_RISK_FACTOR_PAGE_SIZE}",
            field="limit",
        )
    if offset < 0:
        raise ResultStoreContractError("offset must be non-negative", field="offset")
    return limit, offset


def _page(
    rows: Sequence[_T],
    *,
    limit: int,
    offset: int,
) -> tuple[tuple[_T, ...], int | None]:
    page_rows = tuple(rows[offset : offset + limit])
    next_offset = offset + len(page_rows)
    if next_offset >= len(rows):
        return page_rows, None
    return page_rows, next_offset


def _record_search_text(record: RiskFactorMetadataRecord) -> str:
    fields: Iterable[object | None] = (
        record.risk_factor_id.value,
        record.display_name,
        record.risk_class.value,
        record.risk_factor_type.value,
        record.mapping_version,
        _optional_value(record.bucket_id),
        record.bucket_label,
        _optional_value(record.sensitivity_type),
        _optional_value(record.currency),
        _optional_value(record.curve_id),
        _optional_value(record.tenor),
        record.issuer_id,
        record.obligor_id,
        record.counterparty_id,
        record.commodity_id,
        record.equity_id,
        record.status.value,
        record.rfet_evidence_state.value,
        record.modellability_state.value,
        record.nmrf_state.value,
        record.stress_period_id,
        record.source_system,
        record.source_row_id,
    )
    return " ".join(str(field).casefold() for field in fields if field is not None)


def _risk_factor_attribution_rows(
    store: Any,
    run_id: str,
    risk_factor_id: str,
    *,
    framework: FrtbComponent | str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[dict[str, object], ...]:
    if not store.run_exists(run_id):
        return ()
    if not store._has_table_files("capital_attributions"):
        return ()
    if offset < 0:
        raise ResultStoreContractError("offset must be non-negative", field="offset")
    columns = _attribution_columns()
    where = ["a.run_id = ?", "(a.source_id = ? OR a.target_id = ?)"]
    params: list[object] = [run_id, risk_factor_id, risk_factor_id]
    join_clause = _framework_join_clause(store, framework, where, params)
    if join_clause is None:
        return ()
    limit_clause = ""
    if limit is not None:
        limit, offset = _validate_page_window(limit, offset)
        limit_clause = "LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    sql = f"""
        SELECT {", ".join(f"a.{column}" for column in columns)}
        FROM {{table}} a
        {join_clause}
        WHERE {" AND ".join(where)}
        ORDER BY a.node_id, a.attribution_id
        {limit_clause}
    """
    rows = store._fetch_custom(
        sql.format(
            table=store._parquet_relation("capital_attributions"),
            nodes=store._parquet_relation("capital_nodes"),
        ),
        tuple(params),
    )
    return _dict_rows(columns, rows)


def _numeric_or_zero(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _framework_value(framework: FrtbComponent | str | None) -> str | None:
    if framework is None:
        return None
    return FrtbComponent(framework).value


def _optional_value(value: object | None) -> object | None:
    return getattr(value, "value", value)


def _attribution_columns() -> tuple[str, ...]:
    return (
        "run_id",
        "node_id",
        "attribution_id",
        "target_type",
        "target_id",
        "source_id",
        "source_level",
        "method",
        "category",
        "bucket_key",
        "base_amount",
        "marginal_multiplier",
        "contribution",
        "residual",
        "unsupported_reason",
        "artifact_id",
        "metadata_json",
    )


def _framework_join_clause(
    store: Any,
    framework: FrtbComponent | str | None,
    where: list[str],
    params: list[object],
) -> str | None:
    framework_value = _framework_value(framework)
    if framework_value is None:
        return ""
    if not store._has_table_files("capital_nodes"):
        return None
    where.append("n.component = ?")
    params.append(framework_value)
    return "JOIN {nodes} n ON n.run_id = a.run_id AND n.node_id = a.node_id"
