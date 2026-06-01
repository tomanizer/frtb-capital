"""Arrow handoff adapter for SBM delta and GIRR vega batches.

Regulatory traceability:
    ADR 0023 Arrow handoff boundary; Basel MAR21.4-MAR21.7 and
    MAR21.39-MAR21.42 for the downstream GIRR delta capital path; MAR21.90-
    MAR21.95 for the downstream GIRR vega capital path; MAR21.71-MAR21.89 for
    downstream equity, commodity, and FX delta paths.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_handoff_hash,
    validate_arrow_table,
)

from frtb_sbm.batch import (
    SbmSensitivityBatch,
    build_commodity_delta_batch_from_columns,
    build_equity_delta_batch_from_columns,
    build_fx_delta_batch_from_columns,
    build_girr_delta_batch_from_columns,
    build_girr_vega_batch_from_columns,
)
from frtb_sbm.capital import (
    calculate_sbm_capital_from_commodity_delta_batch,
    calculate_sbm_capital_from_equity_delta_batch,
    calculate_sbm_capital_from_fx_delta_batch,
    calculate_sbm_capital_from_girr_delta_batch,
    calculate_sbm_capital_from_girr_vega_batch,
)
from frtb_sbm.data_models import SbmCalculationContext, SbmCapitalResult
from frtb_sbm.validation import SbmInputError

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
    column = table.column(column_name).combine_chunks()
    if pa.types.is_dictionary(column.type):
        column = column.dictionary_decode()
    values = np.asarray(column.to_pylist(), dtype=object)
    values.setflags(write=False)
    return values


def _required_float_column(table: pa.Table, column_name: str) -> npt.NDArray[np.float64]:
    if column_name not in table.column_names:
        raise SbmInputError(f"required column {column_name!r} is missing", field=column_name)
    column = table.column(column_name).combine_chunks()
    try:
        values = np.asarray(column.to_numpy(zero_copy_only=False), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SbmInputError("value must be numeric", field=column_name) from exc
    values.setflags(write=False)
    return values


__all__ = [
    "COMMODITY_DELTA_HANDOFF_COLUMN_SPECS",
    "EQUITY_DELTA_HANDOFF_COLUMN_SPECS",
    "FX_DELTA_HANDOFF_COLUMN_SPECS",
    "GIRR_DELTA_HANDOFF_COLUMN_SPECS",
    "GIRR_VEGA_HANDOFF_COLUMN_SPECS",
    "build_commodity_delta_batch_from_handoff",
    "build_equity_delta_batch_from_handoff",
    "build_fx_delta_batch_from_handoff",
    "build_girr_delta_batch_from_handoff",
    "build_girr_vega_batch_from_handoff",
    "calculate_sbm_capital_from_commodity_delta_handoff",
    "calculate_sbm_capital_from_equity_delta_handoff",
    "calculate_sbm_capital_from_fx_delta_handoff",
    "calculate_sbm_capital_from_girr_delta_handoff",
    "calculate_sbm_capital_from_girr_vega_handoff",
    "normalize_commodity_delta_arrow_table",
    "normalize_equity_delta_arrow_table",
    "normalize_fx_delta_arrow_table",
    "normalize_girr_delta_arrow_table",
    "normalize_girr_vega_arrow_table",
]
