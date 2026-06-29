"""Arrow batch adapters for DRC batches and evidence handoffs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedArrowTable,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
)

from frtb_drc._arrow_hash_adapter import drc_arrow_columnar_input_hash
from frtb_drc.adapters.arrow_evidence import (
    DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS,
    DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS,
    build_drc_ctp_risk_weight_evidence_from_arrow,
    build_drc_fair_value_cap_evidence_from_arrow,
    build_drc_risk_weight_evidence_from_arrow,
    build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow,
    normalize_drc_fair_value_cap_evidence_arrow_table,
    normalize_drc_risk_weight_evidence_arrow_table,
)
from frtb_drc.adapters.path_registry import (
    DRC_CTP_ARROW_COLUMN_SPECS,
    DRC_CTP_PATH,
    DRC_NONSEC_ARROW_COLUMN_SPECS,
    DRC_NONSEC_PATH,
    DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
    DRC_SECURITISATION_NON_CTP_PATH,
    DrcPathSpec,
    get_drc_path_spec,
)
from frtb_drc.adapters.positions import build_drc_nonsec_batch_from_columns
from frtb_drc.assembly.hashes import INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2
from frtb_drc.batch import DrcPositionBatch
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID
from frtb_drc.validation import DrcInputError

_DRC_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "position_id": "position_ids",
    "source_row_id": "source_row_ids",
    "desk_id": "desk_ids",
    "legal_entity": "legal_entities",
    "risk_class": "risk_classes",
    "instrument_type": "instrument_types",
    "default_direction": "default_directions",
    "issuer_id": "issuer_ids",
    "tranche_id": "tranche_ids",
    "index_series_id": "index_series_ids",
    "bucket_key": "bucket_keys",
    "seniority": "seniorities",
    "credit_quality": "credit_qualities",
    "notional": "notionals",
    "market_value": "market_values",
    "cumulative_pnl": "cumulative_pnls",
    "maturity_years": "maturity_years",
    "currency": "currencies",
    "lgd_override": "lgd_overrides",
    "is_defaulted": "is_defaulted",
    "is_gse": "is_gse",
    "is_pse": "is_pse",
    "is_covered_bond": "is_covered_bond",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
}


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("DRC Arrow specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(
    DRC_NONSEC_ARROW_COLUMN_SPECS,
    DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
    DRC_CTP_ARROW_COLUMN_SPECS,
    DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS,
    DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS,
)


def normalize_drc_nonsec_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the DRC non-securitisation contract.

    Parameters
    ----------
    table : pa.Table
        Raw client position table for non-securitisation default risk charge.

    Returns
    -------
    NormalizedArrowTable
        Canonical DRC non-securitisation position handoff.
    """

    return _normalize_drc_path_arrow_table(
        table,
        get_drc_path_spec(DRC_NONSEC_PATH),
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def normalize_drc_securitisation_non_ctp_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the DRC securitisation non-CTP contract.

    Parameters
    ----------
    table : pa.Table
        Raw client position table for securitisation non-CTP DRC.

    Returns
    -------
    NormalizedArrowTable
        Canonical DRC securitisation non-CTP position handoff.
    """

    return _normalize_drc_path_arrow_table(
        table,
        get_drc_path_spec(DRC_SECURITISATION_NON_CTP_PATH),
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def normalize_drc_ctp_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the DRC CTP input contract.

    Parameters
    ----------
    table : pa.Table
        Raw client position table for correlation trading portfolio DRC.

    Returns
    -------
    NormalizedArrowTable
        Canonical DRC CTP position handoff.
    """

    return _normalize_drc_path_arrow_table(
        table,
        get_drc_path_spec(DRC_CTP_PATH),
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def _normalize_drc_path_arrow_table(
    table: pa.Table,
    path_spec: DrcPathSpec,
    diagnostics: Sequence[AdapterDiagnostic],
    metadata: Mapping[str, str] | None,
    rejected: pa.Table | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    return normalize_arrow_table(
        table,
        column_specs=path_spec.arrow_column_specs,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_drc_nonsec_batch_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPositionBatch:
    """Build a DRC-owned non-securitisation batch from normalized Arrow.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical non-securitisation position handoff.

    Returns
    -------
    DrcPositionBatch
        Typed DRC position batch for the non-securitisation calculation path.
    """

    return _build_drc_path_batch_from_arrow(
        handoff,
        get_drc_path_spec(DRC_NONSEC_PATH),
        profile_id=profile_id,
    )


def build_drc_securitisation_non_ctp_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> DrcPositionBatch:
    """Build a DRC-owned securitisation non-CTP batch from normalized Arrow.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical securitisation non-CTP position handoff.

    Returns
    -------
    DrcPositionBatch
        Typed DRC position batch for securitisation non-CTP calculation.
    """

    return _build_drc_path_batch_from_arrow(
        handoff,
        get_drc_path_spec(DRC_SECURITISATION_NON_CTP_PATH),
    )


def build_drc_ctp_batch_from_arrow(handoff: NormalizedArrowTable) -> DrcPositionBatch:
    """Build a DRC-owned CTP batch from a normalized Arrow table.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical CTP position handoff.

    Returns
    -------
    DrcPositionBatch
        Typed DRC position batch for correlation trading portfolio calculation.
    """

    return _build_drc_path_batch_from_arrow(handoff, get_drc_path_spec(DRC_CTP_PATH))


def _build_drc_path_batch_from_arrow(
    handoff: NormalizedArrowTable,
    path_spec: DrcPathSpec,
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPositionBatch:
    table, columns = _read_position_columns(handoff, path_spec.arrow_column_specs)
    input_hash = drc_arrow_columnar_input_hash(table, path_spec.arrow_column_specs)
    kwargs = dict(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics_payload(handoff),
        input_hash=input_hash,
        input_hash_algorithm=INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2,
        copy_arrays=False,
    )
    if path_spec.path == DRC_NONSEC_PATH:
        kwargs["profile_id"] = profile_id
    else:
        kwargs["_expected_risk_class"] = path_spec.risk_class
    return build_drc_nonsec_batch_from_columns(**kwargs)


def _read_position_columns(
    handoff: NormalizedArrowTable,
    specs: tuple[ColumnSpec, ...],
) -> tuple[pa.Table, dict[str, npt.NDArray[Any]]]:
    return _read_handoff_columns(handoff, specs)


def _read_handoff_columns(
    handoff: NormalizedArrowTable,
    specs: tuple[ColumnSpec, ...],
) -> tuple[pa.Table, dict[str, npt.NDArray[Any]]]:
    if not isinstance(handoff, NormalizedArrowTable):
        raise DrcInputError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = read_arrow_columns(table, specs, error=_drc_error)
    return table, columns


def _diagnostics_payload(handoff: NormalizedArrowTable) -> tuple[dict[str, object], ...]:
    return tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)


def _drc_batch_column_kwargs(columns: Mapping[str, object]) -> dict[str, Any]:
    return {
        argument_name: columns.get(column_name)
        for column_name, argument_name in _DRC_BATCH_COLUMN_ARGS.items()
    }


def _drc_error(message: str, _field: str | None) -> DrcInputError:
    return DrcInputError(message)


def _citation_ids_column(values: npt.NDArray[Any] | None) -> tuple[tuple[str, ...], ...] | None:
    if values is None:
        return None
    groups: list[tuple[str, ...]] = []
    for value in values:
        if value is None or not str(value).strip():
            groups.append(("US_NPR_210_SCOPE",))
            continue
        groups.append(tuple(item.strip() for item in str(value).split(",") if item.strip()))
    return tuple(groups)


__all__ = [
    "DRC_CTP_ARROW_COLUMN_SPECS",
    "DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS",
    "DRC_NONSEC_ARROW_COLUMN_SPECS",
    "DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS",
    "DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS",
    "build_drc_ctp_batch_from_arrow",
    "build_drc_ctp_risk_weight_evidence_from_arrow",
    "build_drc_fair_value_cap_evidence_from_arrow",
    "build_drc_nonsec_batch_from_arrow",
    "build_drc_risk_weight_evidence_from_arrow",
    "build_drc_securitisation_non_ctp_batch_from_arrow",
    "build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow",
    "normalize_drc_ctp_arrow_table",
    "normalize_drc_fair_value_cap_evidence_arrow_table",
    "normalize_drc_nonsec_arrow_table",
    "normalize_drc_risk_weight_evidence_arrow_table",
    "normalize_drc_securitisation_non_ctp_arrow_table",
]
