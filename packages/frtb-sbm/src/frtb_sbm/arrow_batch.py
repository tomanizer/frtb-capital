"""Arrow batch adapter for SBM delta, vega, and curvature batches.

Regulatory traceability:
    ADR 0023 Arrow batch boundary; Basel MAR21.4-MAR21.7 and
    MAR21.39-MAR21.42 for the downstream GIRR delta capital path; MAR21.90-
    MAR21.95 for downstream GIRR and non-GIRR vega capital paths; MAR21.71-
    MAR21.89 for downstream equity, commodity, and FX delta paths; MAR21.51-
    MAR21.70 for downstream CSR delta paths; MAR21.5 for downstream curvature
    validation batches.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any, cast

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedArrowTable,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
    UnsupportedRegulatoryFeatureError,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
    unique_non_null_text_values,
)

from frtb_sbm.batch import (
    SbmSensitivityBatch,
    build_commodity_delta_batch_from_columns,
    build_csr_nonsec_delta_batch_from_columns,
    build_csr_sec_ctp_delta_batch_from_columns,
    build_csr_sec_nonctp_delta_batch_from_columns,
    build_equity_delta_batch_from_columns,
    build_fx_delta_batch_from_columns,
    build_girr_curvature_batch_from_columns,
    build_girr_delta_batch_from_columns,
    build_girr_vega_batch_from_columns,
    build_sbm_batch_from_columns,
)
from frtb_sbm.capital import (
    calculate_sbm_capital_from_commodity_curvature_batch,
    calculate_sbm_capital_from_commodity_delta_batch,
    calculate_sbm_capital_from_commodity_vega_batch,
    calculate_sbm_capital_from_csr_nonsec_curvature_batch,
    calculate_sbm_capital_from_csr_nonsec_delta_batch,
    calculate_sbm_capital_from_csr_nonsec_vega_batch,
    calculate_sbm_capital_from_csr_sec_ctp_curvature_batch,
    calculate_sbm_capital_from_csr_sec_ctp_delta_batch,
    calculate_sbm_capital_from_csr_sec_ctp_vega_batch,
    calculate_sbm_capital_from_csr_sec_nonctp_curvature_batch,
    calculate_sbm_capital_from_csr_sec_nonctp_delta_batch,
    calculate_sbm_capital_from_csr_sec_nonctp_vega_batch,
    calculate_sbm_capital_from_equity_curvature_batch,
    calculate_sbm_capital_from_equity_delta_batch,
    calculate_sbm_capital_from_equity_vega_batch,
    calculate_sbm_capital_from_fx_curvature_batch,
    calculate_sbm_capital_from_fx_delta_batch,
    calculate_sbm_capital_from_fx_vega_batch,
    calculate_sbm_capital_from_girr_curvature_batch,
    calculate_sbm_capital_from_girr_delta_batch,
    calculate_sbm_capital_from_girr_vega_batch,
    calculate_sbm_portfolio_capital_from_batches,
)
from frtb_sbm.data_models import (
    SbmBatchPortfolioCalculation,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRiskClass,
    SbmRiskMeasure,
)
from frtb_sbm.validation import SbmInputError, coerce_risk_class, coerce_risk_measure

GIRR_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "sensitivity_id",
        aliases=("sensitivityId",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("source_row_id", aliases=("sourceRowId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("desk_id", aliases=("deskId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("legal_entity", aliases=("legalEntity",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_measure", aliases=("riskMeasure",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("bucket", logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_factor", aliases=("riskFactor",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("amount", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "amount_currency",
        aliases=("amountCurrency",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "sign_convention",
        aliases=("signConvention",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("tenor", logical_type=TabularLogicalType.STRING),
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
        "position_id",
        aliases=("positionId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "qualifier",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "option_tenor",
        aliases=("optionTenor",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "liquidity_horizon_days",
        aliases=("liquidityHorizonDays",),
        logical_type=TabularLogicalType.INTEGER,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "maturity",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "up_shock_amount",
        aliases=("upShockAmount",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "down_shock_amount",
        aliases=("downShockAmount",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

GIRR_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    ColumnSpec(
        "option_tenor",
        aliases=("optionTenor",),
        logical_type=TabularLogicalType.STRING,
    )
    if spec.name == "option_tenor"
    else spec
    for spec in GIRR_DELTA_ARROW_COLUMN_SPECS
)


GIRR_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    replace(spec, required=True, null_policy=NullPolicy.FORBID)
    if spec.name in {"up_shock_amount", "down_shock_amount"}
    else spec
    for spec in GIRR_DELTA_ARROW_COLUMN_SPECS
)


def _delta_column_specs(
    *,
    tenor_required: bool,
    qualifier_required: bool,
) -> tuple[ColumnSpec, ...]:
    specs: list[ColumnSpec] = []
    for spec in GIRR_DELTA_ARROW_COLUMN_SPECS:
        if spec.name == "tenor":
            specs.append(
                replace(
                    spec,
                    required=tenor_required,
                    null_policy=NullPolicy.FORBID if tenor_required else NullPolicy.ALLOW,
                )
            )
        elif spec.name == "qualifier":
            specs.append(
                replace(
                    spec,
                    required=qualifier_required,
                    null_policy=NullPolicy.FORBID if qualifier_required else NullPolicy.ALLOW,
                )
            )
        else:
            specs.append(spec)
    return tuple(specs)


def _vega_column_specs(*, qualifier_required: bool) -> tuple[ColumnSpec, ...]:
    specs: list[ColumnSpec] = []
    for spec in GIRR_DELTA_ARROW_COLUMN_SPECS:
        if spec.name == "tenor":
            specs.append(
                replace(
                    spec,
                    required=False,
                    null_policy=NullPolicy.ALLOW,
                )
            )
        elif spec.name == "option_tenor":
            specs.append(
                replace(
                    spec,
                    required=True,
                    null_policy=NullPolicy.FORBID,
                )
            )
        elif spec.name == "qualifier":
            specs.append(
                replace(
                    spec,
                    required=qualifier_required,
                    null_policy=NullPolicy.FORBID if qualifier_required else NullPolicy.ALLOW,
                )
            )
        else:
            specs.append(spec)
    return tuple(specs)


def _curvature_column_specs(
    *,
    tenor_required: bool,
    qualifier_required: bool,
) -> tuple[ColumnSpec, ...]:
    specs: list[ColumnSpec] = []
    for spec in GIRR_DELTA_ARROW_COLUMN_SPECS:
        if spec.name == "tenor":
            specs.append(
                replace(
                    spec,
                    required=tenor_required,
                    null_policy=NullPolicy.FORBID if tenor_required else NullPolicy.ALLOW,
                )
            )
        elif spec.name == "qualifier":
            specs.append(
                replace(
                    spec,
                    required=qualifier_required,
                    null_policy=NullPolicy.FORBID if qualifier_required else NullPolicy.ALLOW,
                )
            )
        elif spec.name in {"up_shock_amount", "down_shock_amount"}:
            specs.append(replace(spec, required=True, null_policy=NullPolicy.FORBID))
        else:
            specs.append(spec)
    return tuple(specs)


FX_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=False,
    qualifier_required=False,
)

EQUITY_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

COMMODITY_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

FX_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=False,
)

EQUITY_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

COMMODITY_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=False,
)

CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

FX_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=False,
)

EQUITY_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

COMMODITY_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)


_SBM_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "sensitivity_id": "sensitivity_ids",
    "source_row_id": "source_row_ids",
    "desk_id": "desk_ids",
    "legal_entity": "legal_entities",
    "risk_class": "risk_classes",
    "risk_measure": "risk_measures",
    "bucket": "buckets",
    "risk_factor": "risk_factors",
    "amount": "amounts",
    "amount_currency": "amount_currencies",
    "sign_convention": "sign_conventions",
    "tenor": "tenors",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "position_id": "position_ids",
    "qualifier": "qualifiers",
    "option_tenor": "option_tenors",
    "liquidity_horizon_days": "liquidity_horizon_days",
    "maturity": "maturities",
    "up_shock_amount": "up_shock_amounts",
    "down_shock_amount": "down_shock_amounts",
}

_OPTIONAL_FLOAT_COLUMN_NAMES = frozenset({"up_shock_amount", "down_shock_amount"})

_SBM_NULL_DEFAULTS: Mapping[str, object] = {
    column_name: None for column_name in _OPTIONAL_FLOAT_COLUMN_NAMES
}

_SBM_ARROW_SPEC_GROUPS: tuple[tuple[ColumnSpec, ...], ...] = (
    GIRR_DELTA_ARROW_COLUMN_SPECS,
    GIRR_VEGA_ARROW_COLUMN_SPECS,
    GIRR_CURVATURE_ARROW_COLUMN_SPECS,
    FX_DELTA_ARROW_COLUMN_SPECS,
    EQUITY_DELTA_ARROW_COLUMN_SPECS,
    COMMODITY_DELTA_ARROW_COLUMN_SPECS,
    CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS,
    CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS,
    CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS,
    FX_VEGA_ARROW_COLUMN_SPECS,
    EQUITY_VEGA_ARROW_COLUMN_SPECS,
    COMMODITY_VEGA_ARROW_COLUMN_SPECS,
    CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS,
    CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS,
    CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS,
    FX_CURVATURE_ARROW_COLUMN_SPECS,
    EQUITY_CURVATURE_ARROW_COLUMN_SPECS,
    COMMODITY_CURVATURE_ARROW_COLUMN_SPECS,
    CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS,
    CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS,
    CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS,
)


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("SBM Arrow specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(*_SBM_ARROW_SPEC_GROUPS)


def normalize_girr_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM GIRR delta input table contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=GIRR_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_girr_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM GIRR vega handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=GIRR_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_girr_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM GIRR curvature validation contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=GIRR_CURVATURE_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_fx_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM FX curvature handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return _normalize_curvature_arrow_table(
        table,
        column_specs=FX_CURVATURE_ARROW_COLUMN_SPECS,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_equity_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM equity curvature handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return _normalize_curvature_arrow_table(
        table,
        column_specs=EQUITY_CURVATURE_ARROW_COLUMN_SPECS,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_commodity_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM commodity curvature contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return _normalize_curvature_arrow_table(
        table,
        column_specs=COMMODITY_CURVATURE_ARROW_COLUMN_SPECS,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_csr_nonsec_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR non-sec curvature contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return _normalize_curvature_arrow_table(
        table,
        column_specs=CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_csr_sec_nonctp_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR sec non-CTP curvature contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return _normalize_curvature_arrow_table(
        table,
        column_specs=CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_csr_sec_ctp_curvature_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR sec CTP curvature contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return _normalize_curvature_arrow_table(
        table,
        column_specs=CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def _normalize_curvature_arrow_table(
    table: pa.Table,
    *,
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


def normalize_fx_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM FX delta handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=FX_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_equity_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM equity delta handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=EQUITY_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_commodity_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM commodity delta handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=COMMODITY_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_csr_nonsec_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR non-securitisation delta contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_csr_sec_nonctp_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR securitisation non-CTP delta contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_csr_sec_ctp_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR securitisation CTP delta contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_fx_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM FX vega handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=FX_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_equity_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM equity vega handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=EQUITY_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_commodity_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM commodity vega handoff contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=COMMODITY_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_csr_nonsec_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR non-securitisation vega contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_csr_sec_nonctp_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR securitisation non-CTP vega contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_csr_sec_ctp_vega_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the SBM CSR securitisation CTP vega contract.
    Parameters
    ----------
    table, diagnostics, metadata, rejected, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_girr_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned GIRR delta batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=GIRR_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_girr_delta_batch_from_columns,
    )


def build_girr_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned GIRR vega batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=GIRR_VEGA_ARROW_COLUMN_SPECS,
        build_batch=build_girr_vega_batch_from_columns,
    )


def build_girr_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned GIRR curvature batch from a normalized handoff.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.GIRR,
        column_specs=GIRR_CURVATURE_ARROW_COLUMN_SPECS,
        build_batch=build_girr_curvature_batch_from_columns,
    )


def build_fx_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned FX curvature batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.FX,
        column_specs=FX_CURVATURE_ARROW_COLUMN_SPECS,
    )


def build_equity_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned equity curvature batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.EQUITY,
        column_specs=EQUITY_CURVATURE_ARROW_COLUMN_SPECS,
    )


def build_commodity_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned commodity curvature batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.COMMODITY,
        column_specs=COMMODITY_CURVATURE_ARROW_COLUMN_SPECS,
    )


def build_csr_nonsec_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR non-sec curvature batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        column_specs=CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS,
    )


def build_csr_sec_nonctp_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR sec non-CTP curvature batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        column_specs=CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS,
    )


def build_csr_sec_ctp_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR sec CTP curvature batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_curvature_batch_from_arrow(
        handoff,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        column_specs=CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS,
    )


def _build_curvature_batch_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    expected_risk_class: SbmRiskClass,
    column_specs: tuple[ColumnSpec, ...],
    build_batch: Callable[..., SbmSensitivityBatch] = build_sbm_batch_from_columns,
) -> SbmSensitivityBatch:
    builder_kwargs: dict[str, object] = {}
    if build_batch is build_sbm_batch_from_columns:
        builder_kwargs = {
            "expected_risk_class": expected_risk_class,
            "expected_risk_measure": SbmRiskMeasure.CURVATURE,
        }
    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=column_specs,
        build_batch=build_batch,
        builder_kwargs=builder_kwargs,
    )


def build_fx_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned FX delta batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=FX_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_fx_delta_batch_from_columns,
    )


def build_equity_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned equity delta batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=EQUITY_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_equity_delta_batch_from_columns,
    )


def build_commodity_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned commodity delta batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=COMMODITY_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_commodity_delta_batch_from_columns,
    )


def build_csr_nonsec_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR non-securitisation delta batch from an Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_csr_nonsec_delta_batch_from_columns,
    )


def build_csr_sec_nonctp_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation non-CTP delta batch from an Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_csr_sec_nonctp_delta_batch_from_columns,
    )


def build_csr_sec_ctp_delta_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation CTP delta batch from an Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS,
        build_batch=build_csr_sec_ctp_delta_batch_from_columns,
    )


def build_fx_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned FX vega batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_non_girr_vega_batch_from_arrow(
        handoff,
        column_specs=FX_VEGA_ARROW_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.FX,
    )


def build_equity_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned equity vega batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_non_girr_vega_batch_from_arrow(
        handoff,
        column_specs=EQUITY_VEGA_ARROW_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.EQUITY,
    )


def build_commodity_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned commodity vega batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_non_girr_vega_batch_from_arrow(
        handoff,
        column_specs=COMMODITY_VEGA_ARROW_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.COMMODITY,
    )


def build_csr_nonsec_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR non-securitisation vega batch from an Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_non_girr_vega_batch_from_arrow(
        handoff,
        column_specs=CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
    )


def build_csr_sec_nonctp_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation non-CTP vega batch from an Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_non_girr_vega_batch_from_arrow(
        handoff,
        column_specs=CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
    )


def build_csr_sec_ctp_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation CTP vega batch from an Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    return _build_non_girr_vega_batch_from_arrow(
        handoff,
        column_specs=CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
    )


def _build_non_girr_vega_batch_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    column_specs: tuple[ColumnSpec, ...],
    expected_risk_class: SbmRiskClass,
) -> SbmSensitivityBatch:
    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=column_specs,
        build_batch=build_sbm_batch_from_columns,
        builder_kwargs={
            "expected_risk_class": expected_risk_class,
            "expected_risk_measure": SbmRiskMeasure.VEGA,
        },
    )


def _build_sbm_batch_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    column_specs: tuple[ColumnSpec, ...],
    build_batch: Callable[..., SbmSensitivityBatch],
    builder_kwargs: Mapping[str, object] | None = None,
) -> SbmSensitivityBatch:
    if not isinstance(handoff, NormalizedArrowTable):
        raise SbmInputError("handoff must be NormalizedArrowTable", field="handoff")
    table = handoff.accepted
    columns: Mapping[str, object] = read_arrow_columns(
        table,
        column_specs,
        error=_sbm_error,
        null_defaults=_SBM_NULL_DEFAULTS,
    )
    kwargs: dict[str, Any] = dict(builder_kwargs or {})
    kwargs.update(_sbm_batch_column_kwargs(columns, row_count=table.num_rows))
    kwargs.update(
        {
            "source_hash": handoff.source_hash,
            "handoff_hash": normalized_arrow_table_hash(handoff),
            "diagnostics": _diagnostics(handoff),
            "copy_arrays": False,
        }
    )
    return build_batch(**kwargs)


def calculate_sbm_capital_from_girr_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized GIRR delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_girr_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_girr_delta_batch(batch, context=context)


def calculate_sbm_capital_from_girr_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized GIRR vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_girr_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_girr_vega_batch(batch, context=context)


def calculate_sbm_capital_from_girr_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized GIRR curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_girr_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_girr_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_fx_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized FX delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_fx_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_fx_delta_batch(batch, context=context)


def calculate_sbm_capital_from_equity_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized equity delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_equity_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_equity_delta_batch(batch, context=context)


def calculate_sbm_capital_from_commodity_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized commodity delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_commodity_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_commodity_delta_batch(batch, context=context)


def calculate_sbm_capital_from_csr_nonsec_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR non-sec delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_nonsec_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_nonsec_delta_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_nonctp_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec non-CTP delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_sec_nonctp_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_sec_nonctp_delta_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_ctp_delta_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec CTP delta Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_sec_ctp_delta_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_sec_ctp_delta_batch(batch, context=context)


def calculate_sbm_capital_from_fx_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized FX vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_fx_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_fx_vega_batch(batch, context=context)


def calculate_sbm_capital_from_equity_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized equity vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_equity_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_equity_vega_batch(batch, context=context)


def calculate_sbm_capital_from_commodity_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized commodity vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_commodity_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_commodity_vega_batch(batch, context=context)


def calculate_sbm_capital_from_csr_nonsec_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR non-sec vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_nonsec_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_nonsec_vega_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_nonctp_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec non-CTP vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_sec_nonctp_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_sec_nonctp_vega_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_ctp_vega_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec CTP vega Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_sec_ctp_vega_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_sec_ctp_vega_batch(batch, context=context)


def calculate_sbm_capital_from_fx_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized FX curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_fx_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_fx_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_equity_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized equity curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_equity_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_equity_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_commodity_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized commodity curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_commodity_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_commodity_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_csr_nonsec_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR non-sec curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_nonsec_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_nonsec_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_nonctp_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec non-CTP curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_sec_nonctp_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_sec_nonctp_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_ctp_curvature_arrow(
    handoff: NormalizedArrowTable,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec CTP curvature Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_csr_sec_ctp_curvature_batch_from_arrow(handoff)
    return calculate_sbm_capital_from_csr_sec_ctp_curvature_batch(batch, context=context)


def calculate_sbm_portfolio_capital_from_arrow_tables(
    arrow_tables: object | None = None,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmBatchPortfolioCalculation:
    """Calculate portfolio-level SBM capital from normalized Arrow tables.

    Each normalized table must be homogeneous by ``risk_class`` and ``risk_measure``.
    The dispatcher infers the path from Arrow metadata, builds package-owned
    batches, and delegates to the batch portfolio dispatcher without accepted
    input-row dataclass materialization.
    Parameters
    ----------
    arrow_tables : object | None, optional
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmBatchPortfolioCalculation
    """

    if arrow_tables is None:
        raise SbmInputError("arrow_tables are required", field="arrow_tables")
    batches = tuple(
        _build_portfolio_dispatch_batch_from_arrow(arrow_table, index=index)
        for index, arrow_table in enumerate(_coerce_arrow_table_sequence(arrow_tables), start=1)
    )
    return calculate_sbm_portfolio_capital_from_batches(batches, context=context)


def _coerce_arrow_table_sequence(arrow_tables: object) -> tuple[NormalizedArrowTable, ...]:
    if isinstance(arrow_tables, NormalizedArrowTable):
        return (arrow_tables,)
    try:
        candidates: tuple[object, ...] = tuple(arrow_tables)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError(
            "arrow_tables must be an iterable of NormalizedArrowTable objects",
            field="arrow_tables",
        ) from exc
    if not candidates:
        raise SbmInputError("arrow_tables must not be empty", field="arrow_tables")
    for candidate in candidates:
        if not isinstance(candidate, NormalizedArrowTable):
            raise SbmInputError(
                "arrow_tables must contain only NormalizedArrowTable objects",
                field="arrow_tables",
            )
    return cast(tuple[NormalizedArrowTable, ...], candidates)


def _build_portfolio_dispatch_batch_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    index: int,
) -> SbmSensitivityBatch:
    path = _homogeneous_arrow_path(handoff, index=index)
    builder = _ARROW_BATCH_BUILDERS.get(path)
    if builder is None:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm Arrow portfolio dispatcher does not support "
            f"risk_class={path[0].value}, risk_measure={path[1].value}"
        )
    return builder(handoff)


def _homogeneous_arrow_path(
    handoff: NormalizedArrowTable,
    *,
    index: int,
) -> tuple[SbmRiskClass, SbmRiskMeasure]:
    table = handoff.accepted
    if table.num_rows == 0:
        raise SbmInputError(
            f"arrow table {index} accepted table must not be empty",
            field="arrow_table",
        )
    risk_class_values = _unique_arrow_text_values(table, "risk_class", index=index)
    risk_measure_values = _unique_arrow_text_values(table, "risk_measure", index=index)
    if len(risk_class_values) != 1 or len(risk_measure_values) != 1:
        raise SbmInputError(
            f"arrow table {index} must be homogeneous by risk_class and risk_measure",
            field="arrow_table",
        )
    return (
        coerce_risk_class(risk_class_values[0]),
        coerce_risk_measure(risk_measure_values[0]),
    )


def _unique_arrow_text_values(
    table: pa.Table,
    column_name: str,
    *,
    index: int,
) -> tuple[str, ...]:
    if column_name not in table.column_names:
        raise SbmInputError(
            f"arrow table {index} required column {column_name!r} is missing",
            field=column_name,
        )
    try:
        text_values = unique_non_null_text_values(table, column_name)
    except NormalizedTableError as exc:
        raise SbmInputError(str(exc), field=column_name) from exc
    if not text_values:
        raise SbmInputError(
            f"arrow table {index} {column_name} must contain one non-null value",
            field=column_name,
        )
    return text_values


_ARROW_BATCH_BUILDERS: Mapping[
    tuple[SbmRiskClass, SbmRiskMeasure],
    Callable[[NormalizedArrowTable], SbmSensitivityBatch],
] = {
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA): build_girr_delta_batch_from_arrow,
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA): build_girr_vega_batch_from_arrow,
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE): build_girr_curvature_batch_from_arrow,
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA): build_fx_delta_batch_from_arrow,
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA): build_fx_vega_batch_from_arrow,
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE): build_fx_curvature_batch_from_arrow,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA): build_equity_delta_batch_from_arrow,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA): build_equity_vega_batch_from_arrow,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE): (build_equity_curvature_batch_from_arrow),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA): build_commodity_delta_batch_from_arrow,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA): build_commodity_vega_batch_from_arrow,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE): (
        build_commodity_curvature_batch_from_arrow
    ),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA): build_csr_nonsec_delta_batch_from_arrow,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA): build_csr_nonsec_vega_batch_from_arrow,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE): (
        build_csr_nonsec_curvature_batch_from_arrow
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA): (
        build_csr_sec_nonctp_delta_batch_from_arrow
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA): (
        build_csr_sec_nonctp_vega_batch_from_arrow
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE): (
        build_csr_sec_nonctp_curvature_batch_from_arrow
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA): (build_csr_sec_ctp_delta_batch_from_arrow),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA): build_csr_sec_ctp_vega_batch_from_arrow,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE): (
        build_csr_sec_ctp_curvature_batch_from_arrow
    ),
}


def _sbm_batch_column_kwargs(columns: Mapping[str, object], *, row_count: int) -> dict[str, Any]:
    kwargs = {
        argument_name: columns.get(column_name)
        for column_name, argument_name in _SBM_BATCH_COLUMN_ARGS.items()
    }
    if kwargs["tenors"] is None:
        kwargs["tenors"] = (None,) * row_count
    return kwargs


def _sbm_error(message: str, field: str | None) -> SbmInputError:
    if field is not None and message == f"{field} must be numeric":
        message = "value must be numeric"
    return SbmInputError(message, field="" if field is None else field)


def _diagnostics(handoff: NormalizedArrowTable) -> tuple[Mapping[str, object], ...]:
    return tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)


__all__ = [
    "COMMODITY_CURVATURE_ARROW_COLUMN_SPECS",
    "COMMODITY_DELTA_ARROW_COLUMN_SPECS",
    "COMMODITY_VEGA_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS",
    "CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS",
    "CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS",
    "CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS",
    "EQUITY_CURVATURE_ARROW_COLUMN_SPECS",
    "EQUITY_DELTA_ARROW_COLUMN_SPECS",
    "EQUITY_VEGA_ARROW_COLUMN_SPECS",
    "FX_CURVATURE_ARROW_COLUMN_SPECS",
    "FX_DELTA_ARROW_COLUMN_SPECS",
    "FX_VEGA_ARROW_COLUMN_SPECS",
    "GIRR_CURVATURE_ARROW_COLUMN_SPECS",
    "GIRR_DELTA_ARROW_COLUMN_SPECS",
    "GIRR_VEGA_ARROW_COLUMN_SPECS",
    "build_commodity_curvature_batch_from_arrow",
    "build_commodity_delta_batch_from_arrow",
    "build_commodity_vega_batch_from_arrow",
    "build_csr_nonsec_curvature_batch_from_arrow",
    "build_csr_nonsec_delta_batch_from_arrow",
    "build_csr_nonsec_vega_batch_from_arrow",
    "build_csr_sec_ctp_curvature_batch_from_arrow",
    "build_csr_sec_ctp_delta_batch_from_arrow",
    "build_csr_sec_ctp_vega_batch_from_arrow",
    "build_csr_sec_nonctp_curvature_batch_from_arrow",
    "build_csr_sec_nonctp_delta_batch_from_arrow",
    "build_csr_sec_nonctp_vega_batch_from_arrow",
    "build_equity_curvature_batch_from_arrow",
    "build_equity_delta_batch_from_arrow",
    "build_equity_vega_batch_from_arrow",
    "build_fx_curvature_batch_from_arrow",
    "build_fx_delta_batch_from_arrow",
    "build_fx_vega_batch_from_arrow",
    "build_girr_curvature_batch_from_arrow",
    "build_girr_delta_batch_from_arrow",
    "build_girr_vega_batch_from_arrow",
    "calculate_sbm_capital_from_commodity_curvature_arrow",
    "calculate_sbm_capital_from_commodity_delta_arrow",
    "calculate_sbm_capital_from_commodity_vega_arrow",
    "calculate_sbm_capital_from_csr_nonsec_curvature_arrow",
    "calculate_sbm_capital_from_csr_nonsec_delta_arrow",
    "calculate_sbm_capital_from_csr_nonsec_vega_arrow",
    "calculate_sbm_capital_from_csr_sec_ctp_curvature_arrow",
    "calculate_sbm_capital_from_csr_sec_ctp_delta_arrow",
    "calculate_sbm_capital_from_csr_sec_ctp_vega_arrow",
    "calculate_sbm_capital_from_csr_sec_nonctp_curvature_arrow",
    "calculate_sbm_capital_from_csr_sec_nonctp_delta_arrow",
    "calculate_sbm_capital_from_csr_sec_nonctp_vega_arrow",
    "calculate_sbm_capital_from_equity_curvature_arrow",
    "calculate_sbm_capital_from_equity_delta_arrow",
    "calculate_sbm_capital_from_equity_vega_arrow",
    "calculate_sbm_capital_from_fx_curvature_arrow",
    "calculate_sbm_capital_from_fx_delta_arrow",
    "calculate_sbm_capital_from_fx_vega_arrow",
    "calculate_sbm_capital_from_girr_curvature_arrow",
    "calculate_sbm_capital_from_girr_delta_arrow",
    "calculate_sbm_capital_from_girr_vega_arrow",
    "calculate_sbm_portfolio_capital_from_arrow_tables",
    "normalize_commodity_curvature_arrow_table",
    "normalize_commodity_delta_arrow_table",
    "normalize_commodity_vega_arrow_table",
    "normalize_csr_nonsec_curvature_arrow_table",
    "normalize_csr_nonsec_delta_arrow_table",
    "normalize_csr_nonsec_vega_arrow_table",
    "normalize_csr_sec_ctp_curvature_arrow_table",
    "normalize_csr_sec_ctp_delta_arrow_table",
    "normalize_csr_sec_ctp_vega_arrow_table",
    "normalize_csr_sec_nonctp_curvature_arrow_table",
    "normalize_csr_sec_nonctp_delta_arrow_table",
    "normalize_csr_sec_nonctp_vega_arrow_table",
    "normalize_equity_curvature_arrow_table",
    "normalize_equity_delta_arrow_table",
    "normalize_equity_vega_arrow_table",
    "normalize_fx_curvature_arrow_table",
    "normalize_fx_delta_arrow_table",
    "normalize_fx_vega_arrow_table",
    "normalize_girr_curvature_arrow_table",
    "normalize_girr_delta_arrow_table",
    "normalize_girr_vega_arrow_table",
]
