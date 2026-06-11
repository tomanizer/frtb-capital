"""Arrow table assembly for the DRC CRIF ingress adapter."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import NormalizedArrowTable

from frtb_drc._crif_models import DrcCrifAdapterResult, DrcRejectedCrifRow
from frtb_drc.adapters.arrow import (
    normalize_drc_ctp_arrow_table,
    normalize_drc_nonsec_arrow_table,
    normalize_drc_securitisation_non_ctp_arrow_table,
)
from frtb_drc.data_models import (
    CreditQuality,
    DefaultDirection,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
)


def drc_crif_result_to_arrow_tables(
    result: DrcCrifAdapterResult,
) -> Mapping[DrcRiskClass, NormalizedArrowTable]:
    """Build class-specific normalized Arrow tables from accepted CRIF rows.
    Parameters
    ----------
    result : DrcCrifAdapterResult
        DRC capital result to serialize or reconcile.

    Returns
    -------
    Mapping[DrcRiskClass, NormalizedArrowTable]
        Result of the operation.
    """

    by_class: dict[DrcRiskClass, list[DrcPosition]] = {}
    for position in result.positions:
        by_class.setdefault(DrcRiskClass(position.risk_class), []).append(position)

    tables: dict[DrcRiskClass, NormalizedArrowTable] = {}
    for risk_class, positions in sorted(by_class.items(), key=lambda item: item[0].value):
        table = _positions_to_arrow_table(tuple(positions))
        metadata = {
            "adapter": "drc_crif",
            "direction_strategy": result.direction_strategy.value,
            "source_file": result.source_file,
            "source_system": result.source_system,
        }
        rejected_table = _rejected_rows_to_arrow_table(result.rejected_rows)
        if risk_class == DrcRiskClass.NON_SECURITISATION:
            normalized = normalize_drc_nonsec_arrow_table(
                table,
                diagnostics=result.diagnostics,
                metadata=metadata,
                rejected=rejected_table,
                source_hash=result.source_hash,
            )
        elif risk_class == DrcRiskClass.SECURITISATION_NON_CTP:
            normalized = normalize_drc_securitisation_non_ctp_arrow_table(
                table,
                diagnostics=result.diagnostics,
                metadata=metadata,
                rejected=rejected_table,
                source_hash=result.source_hash,
            )
        elif risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
            normalized = normalize_drc_ctp_arrow_table(
                table,
                diagnostics=result.diagnostics,
                metadata=metadata,
                rejected=rejected_table,
                source_hash=result.source_hash,
            )
        else:  # pragma: no cover - DrcPosition coerces the enum before this point.
            continue
        tables[risk_class] = normalized
    return MappingProxyType(tables)


def _positions_to_arrow_table(positions: tuple[DrcPosition, ...]) -> pa.Table:
    columns: dict[str, list[object | None]] = {name: [] for name in _ARROW_POSITION_COLUMNS}
    for position in positions:
        columns["position_id"].append(position.position_id)
        columns["source_row_id"].append(position.source_row_id)
        columns["desk_id"].append(position.desk_id)
        columns["legal_entity"].append(position.legal_entity)
        columns["risk_class"].append(DrcRiskClass(position.risk_class).value)
        columns["instrument_type"].append(DrcInstrumentType(position.instrument_type).value)
        columns["default_direction"].append(DefaultDirection(position.default_direction).value)
        columns["issuer_id"].append(position.issuer_id)
        columns["tranche_id"].append(position.tranche_id)
        columns["index_series_id"].append(position.index_series_id)
        columns["bucket_key"].append(position.bucket_key)
        columns["seniority"].append(
            None if position.seniority is None else DrcSeniority(position.seniority).value
        )
        columns["credit_quality"].append(
            None
            if position.credit_quality is None
            else CreditQuality(position.credit_quality).value
        )
        columns["notional"].append(position.notional)
        columns["market_value"].append(position.market_value)
        columns["cumulative_pnl"].append(position.cumulative_pnl)
        columns["maturity_years"].append(position.maturity_years)
        columns["currency"].append(position.currency)
        columns["lgd_override"].append(position.lgd_override)
        columns["is_defaulted"].append(position.is_defaulted)
        columns["is_gse"].append(position.is_gse)
        columns["is_pse"].append(position.is_pse)
        columns["is_covered_bond"].append(position.is_covered_bond)
        lineage = position.lineage
        columns["lineage_source_system"].append(None if lineage is None else lineage.source_system)
        columns["lineage_source_file"].append(None if lineage is None else lineage.source_file)
        columns["citation_ids"].append(",".join(position.citation_ids))
    return pa.table(columns)


def _rejected_rows_to_arrow_table(rejected_rows: tuple[DrcRejectedCrifRow, ...]) -> pa.Table:
    return pa.table(
        {
            "source_row_id": [row.source_row_id for row in rejected_rows],
            "reason_code": [row.reason_code for row in rejected_rows],
            "message": [row.message for row in rejected_rows],
            "source_columns": [",".join(row.source_columns) for row in rejected_rows],
        }
    )


_ARROW_POSITION_COLUMNS = (
    "position_id",
    "source_row_id",
    "desk_id",
    "legal_entity",
    "risk_class",
    "instrument_type",
    "default_direction",
    "issuer_id",
    "tranche_id",
    "index_series_id",
    "bucket_key",
    "seniority",
    "credit_quality",
    "notional",
    "market_value",
    "cumulative_pnl",
    "maturity_years",
    "currency",
    "lgd_override",
    "is_defaulted",
    "is_gse",
    "is_pse",
    "is_covered_bond",
    "lineage_source_system",
    "lineage_source_file",
    "citation_ids",
)
