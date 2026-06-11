"""Arrow batch adapters for DRC batches and evidence handoffs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedArrowTable,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
)

from frtb_drc.adapters.positions import (
    build_drc_ctp_batch_from_columns,
    build_drc_nonsec_batch_from_columns,
    build_drc_securitisation_non_ctp_batch_from_columns,
)
from frtb_drc.batch import DrcPositionBatch
from frtb_drc.data_models import (
    DrcFairValueCapEvidence,
    DrcRiskClass,
    DrcRiskWeightEvidence,
    DrcSourceLineage,
)
from frtb_drc.fair_value_cap import fair_value_cap_evidence_by_position
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID
from frtb_drc.risk_weight_evidence import risk_weight_evidence_by_position
from frtb_drc.validation import DrcInputError


def _replace_column_spec(
    spec: ColumnSpec,
    *,
    required: bool,
    null_policy: NullPolicy,
) -> ColumnSpec:
    return ColumnSpec(
        spec.name,
        aliases=spec.aliases,
        logical_type=spec.logical_type,
        required=required,
        null_policy=null_policy,
        chunk_policy=spec.chunk_policy,
        dictionary_policy=spec.dictionary_policy,
    )


DRC_NONSEC_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_row_id", aliases=("sourceRowId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("desk_id", aliases=("deskId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("legal_entity", aliases=("legalEntity",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "instrument_type",
        aliases=("instrumentType",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "default_direction",
        aliases=("defaultDirection",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("issuer_id", aliases=("issuerId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "tranche_id",
        aliases=("trancheId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_series_id",
        aliases=("indexSeriesId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("bucket_key", aliases=("bucketKey",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("seniority", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "credit_quality",
        aliases=("creditQuality",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("notional", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "market_value",
        aliases=("marketValue",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "cumulative_pnl",
        aliases=("cumulativePnl", "cumulativePnL"),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("maturity_years", aliases=("maturityYears",), logical_type=TabularLogicalType.FLOAT),
    ColumnSpec("currency", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lgd_override",
        aliases=("lgdOverride",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_defaulted",
        aliases=("isDefaulted",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_gse",
        aliases=("isGse",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_pse",
        aliases=("isPse",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_covered_bond",
        aliases=("isCoveredBond",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "citation_ids",
        aliases=("citationIds",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(spec, required=False, null_policy=NullPolicy.ALLOW)
    if spec.name in {"seniority", "credit_quality"}
    else _replace_column_spec(spec, required=True, null_policy=NullPolicy.ALLOW)
    if spec.name == "issuer_id"
    else spec
    for spec in DRC_NONSEC_ARROW_COLUMN_SPECS
)

DRC_CTP_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(spec, required=False, null_policy=NullPolicy.ALLOW)
    if spec.name in {"seniority", "credit_quality", "issuer_id"}
    else spec
    for spec in DRC_NONSEC_ARROW_COLUMN_SPECS
)

DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_profile_id",
        aliases=("sourceProfileId",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("source_table", aliases=("sourceTable",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_method", aliases=("sourceMethod",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "effective_risk_weight",
        aliases=("effectiveRiskWeight", "risk_weight", "riskWeight"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    ColumnSpec("as_of_date", aliases=("asOfDate",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_id", aliases=("sourceId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("source_row_id", "sourceRowId"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("citation_ids", aliases=("citationIds",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "is_stale",
        aliases=("isStale",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "validation_flags",
        aliases=("validationFlags",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_profile_id",
        aliases=("sourceProfileId",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("eligible", logical_type=TabularLogicalType.BOOLEAN),
    ColumnSpec(
        "fair_value_cap_amount",
        aliases=("fairValueCapAmount",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "eligibility_reason",
        aliases=("eligibilityReason",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("as_of_date", aliases=("asOfDate",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_id", aliases=("sourceId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("source_row_id", "sourceRowId"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("citation_ids", aliases=("citationIds",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "is_stale",
        aliases=("isStale",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "validation_flags",
        aliases=("validationFlags",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

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

    return _normalize_drc_arrow_table(
        table,
        DRC_NONSEC_ARROW_COLUMN_SPECS,
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

    return _normalize_drc_arrow_table(
        table,
        DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
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

    return _normalize_drc_arrow_table(
        table,
        DRC_CTP_ARROW_COLUMN_SPECS,
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def normalize_drc_risk_weight_evidence_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize Arrow risk-weight evidence for DRC securitisation and CTP.

    Parameters
    ----------
    table : pa.Table
        Raw client evidence table.

    Returns
    -------
    NormalizedArrowTable
        Canonical evidence handoff for context-map construction.
    """

    return _normalize_drc_arrow_table(
        table,
        DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS,
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def normalize_drc_fair_value_cap_evidence_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize Arrow fair-value-cap evidence for DRC securitisation.

    Parameters
    ----------
    table : pa.Table
        Raw client evidence table.

    Returns
    -------
    NormalizedArrowTable
        Canonical evidence handoff for context-map construction.
    """

    return _normalize_drc_arrow_table(
        table,
        DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS,
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def _normalize_drc_arrow_table(
    table: pa.Table,
    column_specs: tuple[ColumnSpec, ...],
    diagnostics: Sequence[AdapterDiagnostic],
    metadata: Mapping[str, str] | None,
    rejected: pa.Table | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    return normalize_arrow_table(
        table,
        column_specs=column_specs,
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

    table, columns = _read_position_columns(handoff, DRC_NONSEC_ARROW_COLUMN_SPECS)
    return build_drc_nonsec_batch_from_columns(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics_payload(handoff),
        copy_arrays=False,
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

    table, columns = _read_position_columns(handoff, DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS)
    return build_drc_securitisation_non_ctp_batch_from_columns(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics_payload(handoff),
        copy_arrays=False,
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

    table, columns = _read_position_columns(handoff, DRC_CTP_ARROW_COLUMN_SPECS)
    return build_drc_ctp_batch_from_columns(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics_payload(handoff),
        copy_arrays=False,
    )


def build_drc_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcRiskWeightEvidence]:
    """Build typed DRC risk-weight evidence records from an Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical risk-weight evidence handoff.

    Returns
    -------
    dict[str, DrcRiskWeightEvidence]
        Evidence keyed by position id for context-map injection.
    """

    return _build_drc_risk_weight_evidence_from_arrow(handoff, expected_risk_class=None)


def build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcRiskWeightEvidence]:
    """Build securitisation non-CTP risk-weight evidence from Arrow.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical risk-weight evidence handoff.

    Returns
    -------
    dict[str, DrcRiskWeightEvidence]
        Securitisation non-CTP evidence keyed by position id.
    """

    return _build_drc_risk_weight_evidence_from_arrow(
        handoff,
        expected_risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
    )


def build_drc_ctp_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcRiskWeightEvidence]:
    """Build CTP risk-weight evidence from an Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical risk-weight evidence handoff.

    Returns
    -------
    dict[str, DrcRiskWeightEvidence]
        Correlation trading portfolio evidence keyed by position id.
    """

    return _build_drc_risk_weight_evidence_from_arrow(
        handoff,
        expected_risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )


def build_drc_fair_value_cap_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcFairValueCapEvidence]:
    """Build typed DRC fair-value-cap evidence records from an Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical fair-value-cap evidence handoff.

    Returns
    -------
    dict[str, DrcFairValueCapEvidence]
        Fair-value-cap evidence keyed by position id for context-map injection.
    """

    table, columns = _read_evidence_columns(handoff, DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS)
    records: list[DrcFairValueCapEvidence] = []
    for index in range(table.num_rows):
        position_id = _required_text(columns, "position_id", index)
        eligible = _required_bool(columns, "eligible", index)
        fair_value_cap_amount = _optional_float(columns, "fair_value_cap_amount", index)
        _validate_fair_value_cap_amount(position_id, eligible, fair_value_cap_amount)
        if _optional_bool(columns, "is_stale", index):
            raise DrcInputError(f"fair-value-cap evidence for {position_id!r} is stale")
        records.append(
            DrcFairValueCapEvidence(
                position_id=position_id,
                source_profile_id=_required_text(columns, "source_profile_id", index),
                eligible=eligible,
                fair_value_cap_amount=fair_value_cap_amount,
                eligibility_reason=_required_text(columns, "eligibility_reason", index),
                as_of_date=_required_date(columns, "as_of_date", index),
                source_id=_required_text(columns, "source_id", index),
                lineage=_lineage_from_columns(columns, index),
                citation_ids=_required_ids(columns, "citation_ids", index),
                is_stale=False,
                validation_flags=_optional_ids(columns, "validation_flags", index),
            )
        )
    return fair_value_cap_evidence_by_position(records)


def _build_drc_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    expected_risk_class: DrcRiskClass | None,
) -> dict[str, DrcRiskWeightEvidence]:
    table, columns = _read_evidence_columns(handoff, DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS)
    records: list[DrcRiskWeightEvidence] = []
    for index in range(table.num_rows):
        position_id = _required_text(columns, "position_id", index)
        risk_class = _risk_class(columns, index)
        if expected_risk_class is not None and risk_class is not expected_risk_class:
            raise DrcInputError(
                f"risk-weight evidence for {position_id!r} has risk_class "
                f"{risk_class.value!r}; expected {expected_risk_class.value!r}"
            )
        if _optional_bool(columns, "is_stale", index):
            raise DrcInputError(f"risk-weight evidence for {position_id!r} is stale")
        records.append(
            DrcRiskWeightEvidence(
                position_id=position_id,
                risk_class=risk_class,
                source_profile_id=_required_text(columns, "source_profile_id", index),
                source_table=_required_text(columns, "source_table", index),
                source_method=_required_text(columns, "source_method", index),
                effective_risk_weight=_required_non_negative_float(
                    columns,
                    "effective_risk_weight",
                    index,
                ),
                as_of_date=_required_date(columns, "as_of_date", index),
                source_id=_required_text(columns, "source_id", index),
                lineage=_lineage_from_columns(columns, index),
                citation_ids=_required_ids(columns, "citation_ids", index),
                is_stale=False,
                validation_flags=_optional_ids(columns, "validation_flags", index),
            )
        )
    return risk_weight_evidence_by_position(records)


def _read_position_columns(
    handoff: NormalizedArrowTable,
    specs: tuple[ColumnSpec, ...],
) -> tuple[pa.Table, dict[str, npt.NDArray[Any]]]:
    return _read_handoff_columns(handoff, specs)


def _read_evidence_columns(
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


def _lineage_from_columns(columns: Mapping[str, npt.NDArray[Any]], index: int) -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system=_required_text(columns, "lineage_source_system", index),
        source_file=_required_text(columns, "lineage_source_file", index),
        source_row_id=_required_text(columns, "lineage_source_row_id", index),
        source_column_map={},
    )


def _risk_class(columns: Mapping[str, npt.NDArray[Any]], index: int) -> DrcRiskClass:
    raw = _required_text(columns, "risk_class", index)
    try:
        return DrcRiskClass(raw)
    except ValueError as exc:
        raise DrcInputError(f"risk_class must be a supported DRC risk class: {raw!r}") from exc


def _value(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> object:
    values = columns.get(field)
    if values is None:
        return None
    return values[index]


def _required_text(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> str:
    value = _value(columns, field, index)
    if value is None:
        raise DrcInputError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise DrcInputError(f"{field} must be non-empty")
    return text


def _required_bool(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> bool:
    value = _value(columns, field, index)
    if value is None:
        raise DrcInputError(f"{field} is required")
    return _coerce_bool(value, field)


def _optional_bool(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> bool:
    value = _value(columns, field, index)
    if value is None:
        return False
    return _coerce_bool(value, field)


def _coerce_bool(value: object, field: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n", ""}:
        return False
    raise DrcInputError(f"{field} must be boolean")


def _required_date(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> date:
    value = _value(columns, field, index)
    if value is None:
        raise DrcInputError(f"{field} is required")
    if isinstance(value, date):
        return value
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            raise DrcInputError(f"{field} is required")
        return date.fromisoformat(np.datetime_as_string(value.astype("datetime64[D]"), unit="D"))
    text = str(value).strip()
    if not text:
        raise DrcInputError(f"{field} is required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise DrcInputError(f"{field} must be an ISO date") from exc


def _required_non_negative_float(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> float:
    value = _float_value(_value(columns, field, index), field)
    if value is None:
        raise DrcInputError(f"{field} is required")
    if value < 0.0:
        raise DrcInputError(f"{field} must be non-negative")
    return value


def _optional_float(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> float | None:
    return _float_value(_value(columns, field, index), field)


def _float_value(value: object, field: str) -> float | None:
    if value is None:
        return None
    result = float(cast(Any, value))
    if np.isnan(result):
        return None
    if not np.isfinite(result):
        raise DrcInputError(f"{field} must be finite")
    return result


def _validate_fair_value_cap_amount(
    position_id: str,
    eligible: bool,
    fair_value_cap_amount: float | None,
) -> None:
    if eligible and fair_value_cap_amount is None:
        raise DrcInputError(
            f"fair_value_cap_amount is required for eligible evidence {position_id!r}"
        )
    if eligible and fair_value_cap_amount is not None and fair_value_cap_amount < 0.0:
        raise DrcInputError(f"fair_value_cap_amount must be non-negative for {position_id!r}")
    if not eligible and fair_value_cap_amount is not None:
        raise DrcInputError(
            f"fair_value_cap_amount must be empty for ineligible evidence {position_id!r}"
        )


def _required_ids(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> tuple[str, ...]:
    ids = _optional_ids(columns, field, index)
    if not ids:
        raise DrcInputError(f"{field} must contain at least one non-empty id")
    return ids


def _optional_ids(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> tuple[str, ...]:
    value = _value(columns, field, index)
    if value is None:
        return ()
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


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
