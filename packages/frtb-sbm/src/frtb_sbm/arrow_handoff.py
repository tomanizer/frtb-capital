"""Arrow handoff adapter for SBM delta, vega, and curvature batches.

Regulatory traceability:
    ADR 0023 Arrow handoff boundary; Basel MAR21.4-MAR21.7 and
    MAR21.39-MAR21.42 for the downstream GIRR delta capital path; MAR21.90-
    MAR21.95 for downstream GIRR and non-GIRR vega capital paths; MAR21.71-
    MAR21.89 for downstream equity, commodity, and FX delta paths; MAR21.51-
    MAR21.70 for downstream CSR delta paths; MAR21.5 for downstream curvature
    validation handoffs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularLogicalType,
    UnsupportedRegulatoryFeatureError,
    normalize_arrow_table,
    normalized_handoff_hash,
    validate_arrow_table,
)

from frtb_sbm.batch import (
    SbmSensitivityBatch,
    build_commodity_delta_batch_from_columns,
    build_csr_nonsec_delta_batch_from_columns,
    build_csr_sec_ctp_delta_batch_from_columns,
    build_csr_sec_nonctp_delta_batch_from_columns,
    build_equity_delta_batch_from_columns,
    build_fx_delta_batch_from_columns,
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

GIRR_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
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

GIRR_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    ColumnSpec(
        "option_tenor",
        aliases=("optionTenor",),
        logical_type=TabularLogicalType.STRING,
    )
    if spec.name == "option_tenor"
    else spec
    for spec in GIRR_DELTA_HANDOFF_COLUMN_SPECS
)


GIRR_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    replace(spec, required=True, null_policy=NullPolicy.FORBID)
    if spec.name in {"up_shock_amount", "down_shock_amount"}
    else spec
    for spec in GIRR_DELTA_HANDOFF_COLUMN_SPECS
)


def _delta_column_specs(
    *,
    tenor_required: bool,
    qualifier_required: bool,
) -> tuple[ColumnSpec, ...]:
    specs: list[ColumnSpec] = []
    for spec in GIRR_DELTA_HANDOFF_COLUMN_SPECS:
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
    for spec in GIRR_DELTA_HANDOFF_COLUMN_SPECS:
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
    for spec in GIRR_DELTA_HANDOFF_COLUMN_SPECS:
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


FX_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=False,
    qualifier_required=False,
)

EQUITY_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

COMMODITY_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

CSR_NONSEC_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

CSR_SEC_NONCTP_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

CSR_SEC_CTP_DELTA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _delta_column_specs(
    tenor_required=True,
    qualifier_required=True,
)

FX_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=False,
)

EQUITY_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

COMMODITY_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=False,
)

CSR_NONSEC_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

CSR_SEC_NONCTP_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

CSR_SEC_CTP_VEGA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _vega_column_specs(
    qualifier_required=True,
)

FX_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=False,
)

EQUITY_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

COMMODITY_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

CSR_NONSEC_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

CSR_SEC_NONCTP_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)

CSR_SEC_CTP_CURVATURE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = _curvature_column_specs(
    tenor_required=False,
    qualifier_required=True,
)


def normalize_girr_delta_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM GIRR delta handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=GIRR_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM GIRR vega handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=GIRR_VEGA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM GIRR curvature validation contract."""

    return normalize_arrow_table(
        table,
        column_specs=GIRR_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM FX curvature handoff contract."""

    return _normalize_curvature_arrow_table(
        table,
        column_specs=FX_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM equity curvature handoff contract."""

    return _normalize_curvature_arrow_table(
        table,
        column_specs=EQUITY_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM commodity curvature contract."""

    return _normalize_curvature_arrow_table(
        table,
        column_specs=COMMODITY_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR non-sec curvature contract."""

    return _normalize_curvature_arrow_table(
        table,
        column_specs=CSR_NONSEC_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR sec non-CTP curvature contract."""

    return _normalize_curvature_arrow_table(
        table,
        column_specs=CSR_SEC_NONCTP_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR sec CTP curvature contract."""

    return _normalize_curvature_arrow_table(
        table,
        column_specs=CSR_SEC_CTP_CURVATURE_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM FX delta handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=FX_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM equity delta handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=EQUITY_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM commodity delta handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=COMMODITY_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR non-securitisation delta contract."""

    return normalize_arrow_table(
        table,
        column_specs=CSR_NONSEC_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR securitisation non-CTP delta contract."""

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_NONCTP_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR securitisation CTP delta contract."""

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_CTP_DELTA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM FX vega handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=FX_VEGA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM equity vega handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=EQUITY_VEGA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM commodity vega handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=COMMODITY_VEGA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR non-securitisation vega contract."""

    return normalize_arrow_table(
        table,
        column_specs=CSR_NONSEC_VEGA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR securitisation non-CTP vega contract."""

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_NONCTP_VEGA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the SBM CSR securitisation CTP vega contract."""

    return normalize_arrow_table(
        table,
        column_specs=CSR_SEC_CTP_VEGA_HANDOFF_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_girr_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned GIRR delta batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=GIRR_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_girr_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_required_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_optional_object_column(table, "qualifier"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_girr_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned GIRR vega batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=GIRR_VEGA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_girr_vega_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_required_object_column(table, "tenor"),
        option_tenors=_required_object_column(table, "option_tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_optional_object_column(table, "qualifier"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_girr_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned GIRR curvature batch from a normalized handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.GIRR,
        column_specs=GIRR_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=True,
        qualifier_required=False,
    )


def build_fx_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned FX curvature batch from a normalized Arrow handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.FX,
        column_specs=FX_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=False,
        qualifier_required=False,
    )


def build_equity_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned equity curvature batch from a normalized Arrow handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.EQUITY,
        column_specs=EQUITY_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=False,
        qualifier_required=True,
    )


def build_commodity_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned commodity curvature batch from a normalized Arrow handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.COMMODITY,
        column_specs=COMMODITY_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=False,
        qualifier_required=True,
    )


def build_csr_nonsec_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR non-sec curvature batch from a normalized Arrow handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        column_specs=CSR_NONSEC_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=False,
        qualifier_required=True,
    )


def build_csr_sec_nonctp_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR sec non-CTP curvature batch from a normalized Arrow handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        column_specs=CSR_SEC_NONCTP_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=False,
        qualifier_required=True,
    )


def build_csr_sec_ctp_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR sec CTP curvature batch from a normalized Arrow handoff."""

    return _build_curvature_batch_from_handoff(
        handoff,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        column_specs=CSR_SEC_CTP_CURVATURE_HANDOFF_COLUMN_SPECS,
        tenor_required=False,
        qualifier_required=True,
    )


def _build_curvature_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    expected_risk_class: SbmRiskClass,
    column_specs: tuple[ColumnSpec, ...],
    tenor_required: bool,
    qualifier_required: bool,
) -> SbmSensitivityBatch:
    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=column_specs)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_sbm_batch_from_columns(
        expected_risk_class=expected_risk_class,
        expected_risk_measure=SbmRiskMeasure.CURVATURE,
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=(
            _required_object_column(table, "tenor")
            if tenor_required
            else _optional_or_null_object_column(table, "tenor")
        ),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=(
            _required_object_column(table, "qualifier")
            if qualifier_required
            else _optional_object_column(table, "qualifier")
        ),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_required_float_column(table, "up_shock_amount"),
        down_shock_amounts=_required_float_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_fx_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned FX delta batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=FX_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_fx_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_optional_or_null_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_optional_object_column(table, "qualifier"),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_equity_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned equity delta batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=EQUITY_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_equity_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_optional_or_null_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_required_object_column(table, "qualifier"),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_commodity_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned commodity delta batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=COMMODITY_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_commodity_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_required_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_required_object_column(table, "qualifier"),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_csr_nonsec_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR non-securitisation delta batch from an Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=CSR_NONSEC_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_csr_nonsec_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_required_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_required_object_column(table, "qualifier"),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_csr_sec_nonctp_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation non-CTP delta batch from an Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=CSR_SEC_NONCTP_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_csr_sec_nonctp_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_required_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_required_object_column(table, "qualifier"),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_csr_sec_ctp_delta_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation CTP delta batch from an Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=CSR_SEC_CTP_DELTA_HANDOFF_COLUMN_SPECS)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_csr_sec_ctp_delta_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_required_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_required_object_column(table, "qualifier"),
        option_tenors=_optional_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def build_fx_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned FX vega batch from a normalized Arrow handoff."""

    return _build_non_girr_vega_batch_from_handoff(
        handoff,
        column_specs=FX_VEGA_HANDOFF_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.FX,
    )


def build_equity_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned equity vega batch from a normalized Arrow handoff."""

    return _build_non_girr_vega_batch_from_handoff(
        handoff,
        column_specs=EQUITY_VEGA_HANDOFF_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.EQUITY,
    )


def build_commodity_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned commodity vega batch from a normalized Arrow handoff."""

    return _build_non_girr_vega_batch_from_handoff(
        handoff,
        column_specs=COMMODITY_VEGA_HANDOFF_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.COMMODITY,
    )


def build_csr_nonsec_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR non-securitisation vega batch from an Arrow handoff."""

    return _build_non_girr_vega_batch_from_handoff(
        handoff,
        column_specs=CSR_NONSEC_VEGA_HANDOFF_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
    )


def build_csr_sec_nonctp_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation non-CTP vega batch from an Arrow handoff."""

    return _build_non_girr_vega_batch_from_handoff(
        handoff,
        column_specs=CSR_SEC_NONCTP_VEGA_HANDOFF_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
    )


def build_csr_sec_ctp_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SbmSensitivityBatch:
    """Build an SBM-owned CSR securitisation CTP vega batch from an Arrow handoff."""

    return _build_non_girr_vega_batch_from_handoff(
        handoff,
        column_specs=CSR_SEC_CTP_VEGA_HANDOFF_COLUMN_SPECS,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
    )


def _build_non_girr_vega_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    column_specs: tuple[ColumnSpec, ...],
    expected_risk_class: SbmRiskClass,
) -> SbmSensitivityBatch:
    if not isinstance(handoff, NormalizedTabularHandoff):
        raise SbmInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=column_specs)
    diagnostic_payloads = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_sbm_batch_from_columns(
        expected_risk_class=expected_risk_class,
        expected_risk_measure=SbmRiskMeasure.VEGA,
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        buckets=_required_object_column(table, "bucket"),
        risk_factors=_required_object_column(table, "risk_factor"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        tenors=_optional_or_null_object_column(table, "tenor"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostic_payloads,
        position_ids=_optional_object_column(table, "position_id"),
        qualifiers=_optional_object_column(table, "qualifier"),
        option_tenors=_required_object_column(table, "option_tenor"),
        liquidity_horizon_days=_optional_object_column(table, "liquidity_horizon_days"),
        maturities=_optional_object_column(table, "maturity"),
        up_shock_amounts=_optional_object_column(table, "up_shock_amount"),
        down_shock_amounts=_optional_object_column(table, "down_shock_amount"),
        copy_arrays=False,
    )


def calculate_sbm_capital_from_girr_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized GIRR delta Arrow handoff."""

    batch = build_girr_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_girr_delta_batch(batch, context=context)


def calculate_sbm_capital_from_girr_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized GIRR vega Arrow handoff."""

    batch = build_girr_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_girr_vega_batch(batch, context=context)


def calculate_sbm_capital_from_girr_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized GIRR curvature Arrow handoff."""

    batch = build_girr_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_girr_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_fx_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized FX delta Arrow handoff."""

    batch = build_fx_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_fx_delta_batch(batch, context=context)


def calculate_sbm_capital_from_equity_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized equity delta Arrow handoff."""

    batch = build_equity_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_equity_delta_batch(batch, context=context)


def calculate_sbm_capital_from_commodity_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized commodity delta Arrow handoff."""

    batch = build_commodity_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_commodity_delta_batch(batch, context=context)


def calculate_sbm_capital_from_csr_nonsec_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR non-sec delta Arrow handoff."""

    batch = build_csr_nonsec_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_nonsec_delta_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_nonctp_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec non-CTP delta Arrow handoff."""

    batch = build_csr_sec_nonctp_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_sec_nonctp_delta_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_ctp_delta_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec CTP delta Arrow handoff."""

    batch = build_csr_sec_ctp_delta_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_sec_ctp_delta_batch(batch, context=context)


def calculate_sbm_capital_from_fx_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized FX vega Arrow handoff."""

    batch = build_fx_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_fx_vega_batch(batch, context=context)


def calculate_sbm_capital_from_equity_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized equity vega Arrow handoff."""

    batch = build_equity_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_equity_vega_batch(batch, context=context)


def calculate_sbm_capital_from_commodity_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized commodity vega Arrow handoff."""

    batch = build_commodity_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_commodity_vega_batch(batch, context=context)


def calculate_sbm_capital_from_csr_nonsec_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR non-sec vega Arrow handoff."""

    batch = build_csr_nonsec_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_nonsec_vega_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_nonctp_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec non-CTP vega Arrow handoff."""

    batch = build_csr_sec_nonctp_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_sec_nonctp_vega_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_ctp_vega_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec CTP vega Arrow handoff."""

    batch = build_csr_sec_ctp_vega_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_sec_ctp_vega_batch(batch, context=context)


def calculate_sbm_capital_from_fx_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized FX curvature Arrow handoff."""

    batch = build_fx_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_fx_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_equity_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized equity curvature Arrow handoff."""

    batch = build_equity_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_equity_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_commodity_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized commodity curvature Arrow handoff."""

    batch = build_commodity_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_commodity_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_csr_nonsec_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR non-sec curvature Arrow handoff."""

    batch = build_csr_nonsec_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_nonsec_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_nonctp_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec non-CTP curvature Arrow handoff."""

    batch = build_csr_sec_nonctp_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_sec_nonctp_curvature_batch(batch, context=context)


def calculate_sbm_capital_from_csr_sec_ctp_curvature_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from a normalized CSR sec CTP curvature Arrow handoff."""

    batch = build_csr_sec_ctp_curvature_batch_from_handoff(handoff)
    return calculate_sbm_capital_from_csr_sec_ctp_curvature_batch(batch, context=context)


def calculate_sbm_portfolio_capital_from_handoffs(
    handoffs: object | None = None,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmBatchPortfolioCalculation:
    """
    Calculate portfolio-level SBM capital from normalized Arrow handoffs.

    Each handoff must be homogeneous by ``risk_class`` and ``risk_measure``.
    The dispatcher infers the path from Arrow metadata, builds package-owned
    batches, and delegates to the batch portfolio dispatcher without accepted
    input-row dataclass materialization.
    """

    if handoffs is None:
        raise SbmInputError("handoffs are required", field="handoffs")
    batches = tuple(
        _build_portfolio_dispatch_batch_from_handoff(handoff, index=index)
        for index, handoff in enumerate(_coerce_handoff_sequence(handoffs), start=1)
    )
    return calculate_sbm_portfolio_capital_from_batches(batches, context=context)


def _coerce_handoff_sequence(handoffs: object) -> tuple[NormalizedTabularHandoff, ...]:
    if isinstance(handoffs, NormalizedTabularHandoff):
        return (handoffs,)
    try:
        candidates: tuple[object, ...] = tuple(handoffs)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError(
            "handoffs must be an iterable of NormalizedTabularHandoff objects"
        ) from exc
    if not candidates:
        raise SbmInputError("handoffs must not be empty", field="handoffs")
    for candidate in candidates:
        if not isinstance(candidate, NormalizedTabularHandoff):
            raise SbmInputError("handoffs must contain only NormalizedTabularHandoff objects")
    return cast(tuple[NormalizedTabularHandoff, ...], candidates)


def _build_portfolio_dispatch_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    index: int,
) -> SbmSensitivityBatch:
    path = _homogeneous_handoff_path(handoff, index=index)
    builder = _HANDOFF_BATCH_BUILDERS.get(path)
    if builder is None:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm Arrow portfolio dispatcher does not support "
            f"risk_class={path[0].value}, risk_measure={path[1].value}"
        )
    return builder(handoff)


def _homogeneous_handoff_path(
    handoff: NormalizedTabularHandoff,
    *,
    index: int,
) -> tuple[SbmRiskClass, SbmRiskMeasure]:
    table = handoff.accepted
    if table.num_rows == 0:
        raise SbmInputError(
            f"handoff {index} accepted table must not be empty",
            field="handoff",
        )
    risk_class_values = _unique_handoff_text_values(table, "risk_class", index=index)
    risk_measure_values = _unique_handoff_text_values(table, "risk_measure", index=index)
    if len(risk_class_values) != 1 or len(risk_measure_values) != 1:
        raise SbmInputError(
            f"handoff {index} must be homogeneous by risk_class and risk_measure",
            field="handoff",
        )
    return (
        coerce_risk_class(risk_class_values[0]),
        coerce_risk_measure(risk_measure_values[0]),
    )


def _unique_handoff_text_values(
    table: pa.Table,
    column_name: str,
    *,
    index: int,
) -> tuple[str, ...]:
    if column_name not in table.column_names:
        raise SbmInputError(
            f"handoff {index} required column {column_name!r} is missing",
            field=column_name,
        )
    unique_values = pc.drop_null(pc.unique(table[column_name]))
    text_values = tuple(
        str(unique_values[item_index].as_py()) for item_index in range(len(unique_values))
    )
    if not text_values:
        raise SbmInputError(
            f"handoff {index} {column_name} must contain one non-null value",
            field=column_name,
        )
    return text_values


_HANDOFF_BATCH_BUILDERS: Mapping[
    tuple[SbmRiskClass, SbmRiskMeasure],
    Callable[[NormalizedTabularHandoff], SbmSensitivityBatch],
] = {
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA): build_girr_delta_batch_from_handoff,
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA): build_girr_vega_batch_from_handoff,
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE): build_girr_curvature_batch_from_handoff,
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA): build_fx_delta_batch_from_handoff,
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA): build_fx_vega_batch_from_handoff,
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE): build_fx_curvature_batch_from_handoff,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA): build_equity_delta_batch_from_handoff,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA): build_equity_vega_batch_from_handoff,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE): (build_equity_curvature_batch_from_handoff),
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA): build_commodity_delta_batch_from_handoff,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA): build_commodity_vega_batch_from_handoff,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE): (
        build_commodity_curvature_batch_from_handoff
    ),
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA): build_csr_nonsec_delta_batch_from_handoff,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA): build_csr_nonsec_vega_batch_from_handoff,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE): (
        build_csr_nonsec_curvature_batch_from_handoff
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA): (
        build_csr_sec_nonctp_delta_batch_from_handoff
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA): (
        build_csr_sec_nonctp_vega_batch_from_handoff
    ),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE): (
        build_csr_sec_nonctp_curvature_batch_from_handoff
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA): (build_csr_sec_ctp_delta_batch_from_handoff),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA): build_csr_sec_ctp_vega_batch_from_handoff,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE): (
        build_csr_sec_ctp_curvature_batch_from_handoff
    ),
}


def _required_object_column(table: pa.Table, column_name: str) -> npt.NDArray[np.object_]:
    return _object_column(table, column_name, required=True)  # type: ignore[return-value]


def _optional_object_column(
    table: pa.Table,
    column_name: str,
) -> npt.NDArray[np.object_] | None:
    return _object_column(table, column_name, required=False)


def _optional_or_null_object_column(
    table: pa.Table,
    column_name: str,
) -> npt.NDArray[np.object_]:
    values = _optional_object_column(table, column_name)
    if values is not None:
        return values
    null_values = np.full(table.num_rows, None, dtype=object)
    null_values.setflags(write=False)
    return null_values


def _object_column(
    table: pa.Table,
    column_name: str,
    *,
    required: bool,
) -> npt.NDArray[np.object_] | None:
    if column_name not in table.column_names:
        if required:
            raise SbmInputError(f"required column {column_name!r} is missing", field=column_name)
        return None
    column = table.column(column_name)
    values = _object_array_from_arrow_column(column)
    values.setflags(write=False)
    return values


def _required_float_column(table: pa.Table, column_name: str) -> npt.NDArray[np.float64]:
    if column_name not in table.column_names:
        raise SbmInputError(f"required column {column_name!r} is missing", field=column_name)
    column = table.column(column_name)
    if column.null_count:
        raise SbmInputError(
            "required numeric column must not contain nulls",
            field=column_name,
        )
    values = _float64_array_from_arrow_column(column, field=column_name)
    values.setflags(write=False)
    return values


def _object_array_from_arrow_column(column: pa.ChunkedArray) -> npt.NDArray[np.object_]:
    arrays = tuple(_object_array_from_arrow_array(chunk) for chunk in column.chunks)
    if not arrays:
        return np.empty(0, dtype=object)
    if len(arrays) == 1:
        return arrays[0]
    return np.concatenate(arrays).astype(object, copy=False)


def _object_array_from_arrow_array(array: pa.Array) -> npt.NDArray[np.object_]:
    if pa.types.is_dictionary(array.type):
        return _dictionary_array_to_object_array(cast(pa.DictionaryArray, array))
    return np.asarray(array.to_numpy(zero_copy_only=False), dtype=object)


def _dictionary_array_to_object_array(array: pa.DictionaryArray) -> npt.NDArray[np.object_]:
    if len(array) == 0:
        return np.empty(0, dtype=object)
    dictionary = np.asarray(array.dictionary.to_numpy(zero_copy_only=False), dtype=object)
    indices = np.asarray(
        pc.fill_null(array.indices, pa.scalar(0, type=array.indices.type)).to_numpy(
            zero_copy_only=False
        ),
        dtype=np.int64,
    )
    valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
    values = np.empty(len(array), dtype=object)
    values[valid] = dictionary[indices[valid]]
    values[~valid] = None
    return values


def _float64_array_from_arrow_column(
    column: pa.ChunkedArray,
    *,
    field: str,
) -> npt.NDArray[np.float64]:
    if len(column) == 0:
        return np.empty(0, dtype=np.float64)
    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    if not pa.types.is_float64(array.type):
        try:
            array = cast(pa.Array, pc.cast(array, pa.float64()))
        except (pa.ArrowInvalid, TypeError, ValueError) as exc:
            raise SbmInputError("value must be numeric", field=field) from exc
    try:
        return cast(npt.NDArray[np.float64], array.to_numpy(zero_copy_only=True))
    except (pa.ArrowInvalid, TypeError, ValueError):
        return np.asarray(array.to_numpy(zero_copy_only=False), dtype=np.float64)


__all__ = [
    "COMMODITY_CURVATURE_HANDOFF_COLUMN_SPECS",
    "COMMODITY_DELTA_HANDOFF_COLUMN_SPECS",
    "COMMODITY_VEGA_HANDOFF_COLUMN_SPECS",
    "CSR_NONSEC_CURVATURE_HANDOFF_COLUMN_SPECS",
    "CSR_NONSEC_DELTA_HANDOFF_COLUMN_SPECS",
    "CSR_NONSEC_VEGA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_CTP_CURVATURE_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_CTP_DELTA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_CTP_VEGA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_NONCTP_CURVATURE_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_NONCTP_DELTA_HANDOFF_COLUMN_SPECS",
    "CSR_SEC_NONCTP_VEGA_HANDOFF_COLUMN_SPECS",
    "EQUITY_CURVATURE_HANDOFF_COLUMN_SPECS",
    "EQUITY_DELTA_HANDOFF_COLUMN_SPECS",
    "EQUITY_VEGA_HANDOFF_COLUMN_SPECS",
    "FX_CURVATURE_HANDOFF_COLUMN_SPECS",
    "FX_DELTA_HANDOFF_COLUMN_SPECS",
    "FX_VEGA_HANDOFF_COLUMN_SPECS",
    "GIRR_CURVATURE_HANDOFF_COLUMN_SPECS",
    "GIRR_DELTA_HANDOFF_COLUMN_SPECS",
    "GIRR_VEGA_HANDOFF_COLUMN_SPECS",
    "build_commodity_curvature_batch_from_handoff",
    "build_commodity_delta_batch_from_handoff",
    "build_commodity_vega_batch_from_handoff",
    "build_csr_nonsec_curvature_batch_from_handoff",
    "build_csr_nonsec_delta_batch_from_handoff",
    "build_csr_nonsec_vega_batch_from_handoff",
    "build_csr_sec_ctp_curvature_batch_from_handoff",
    "build_csr_sec_ctp_delta_batch_from_handoff",
    "build_csr_sec_ctp_vega_batch_from_handoff",
    "build_csr_sec_nonctp_curvature_batch_from_handoff",
    "build_csr_sec_nonctp_delta_batch_from_handoff",
    "build_csr_sec_nonctp_vega_batch_from_handoff",
    "build_equity_curvature_batch_from_handoff",
    "build_equity_delta_batch_from_handoff",
    "build_equity_vega_batch_from_handoff",
    "build_fx_curvature_batch_from_handoff",
    "build_fx_delta_batch_from_handoff",
    "build_fx_vega_batch_from_handoff",
    "build_girr_curvature_batch_from_handoff",
    "build_girr_delta_batch_from_handoff",
    "build_girr_vega_batch_from_handoff",
    "calculate_sbm_capital_from_commodity_curvature_handoff",
    "calculate_sbm_capital_from_commodity_delta_handoff",
    "calculate_sbm_capital_from_commodity_vega_handoff",
    "calculate_sbm_capital_from_csr_nonsec_curvature_handoff",
    "calculate_sbm_capital_from_csr_nonsec_delta_handoff",
    "calculate_sbm_capital_from_csr_nonsec_vega_handoff",
    "calculate_sbm_capital_from_csr_sec_ctp_curvature_handoff",
    "calculate_sbm_capital_from_csr_sec_ctp_delta_handoff",
    "calculate_sbm_capital_from_csr_sec_ctp_vega_handoff",
    "calculate_sbm_capital_from_csr_sec_nonctp_curvature_handoff",
    "calculate_sbm_capital_from_csr_sec_nonctp_delta_handoff",
    "calculate_sbm_capital_from_csr_sec_nonctp_vega_handoff",
    "calculate_sbm_capital_from_equity_curvature_handoff",
    "calculate_sbm_capital_from_equity_delta_handoff",
    "calculate_sbm_capital_from_equity_vega_handoff",
    "calculate_sbm_capital_from_fx_curvature_handoff",
    "calculate_sbm_capital_from_fx_delta_handoff",
    "calculate_sbm_capital_from_fx_vega_handoff",
    "calculate_sbm_capital_from_girr_curvature_handoff",
    "calculate_sbm_capital_from_girr_delta_handoff",
    "calculate_sbm_capital_from_girr_vega_handoff",
    "calculate_sbm_portfolio_capital_from_handoffs",
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
