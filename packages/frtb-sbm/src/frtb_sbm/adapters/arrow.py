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
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
    unique_non_null_text_values,
)

from frtb_sbm._arrow_hash_adapter import sbm_arrow_columnar_input_hash
from frtb_sbm.adapters.sensitivities import build_sbm_batch_from_columns
from frtb_sbm.assembly.hashes import INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.capital import (
    calculate_sbm_capital_from_batch,
)
from frtb_sbm.data_models import (
    SbmBatchPortfolioCalculation,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRiskClass,
    SbmRiskMeasure,
)
from frtb_sbm.kernel.portfolio import calculate_sbm_portfolio_capital_from_batches
from frtb_sbm.registry import sbm_batch_spec
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

_ARROW_COLUMN_SPECS_BY_PATH: Mapping[
    tuple[SbmRiskClass, SbmRiskMeasure], tuple[ColumnSpec, ...]
] = {
    (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA): GIRR_DELTA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA): GIRR_VEGA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE): GIRR_CURVATURE_ARROW_COLUMN_SPECS,
    (SbmRiskClass.FX, SbmRiskMeasure.DELTA): FX_DELTA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.FX, SbmRiskMeasure.VEGA): FX_VEGA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.FX, SbmRiskMeasure.CURVATURE): FX_CURVATURE_ARROW_COLUMN_SPECS,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA): EQUITY_DELTA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA): EQUITY_VEGA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE): EQUITY_CURVATURE_ARROW_COLUMN_SPECS,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA): COMMODITY_DELTA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA): COMMODITY_VEGA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE): COMMODITY_CURVATURE_ARROW_COLUMN_SPECS,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA): CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA): CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE): CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS,
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA): (CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA): (CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS),
    (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE): (
        CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS
    ),
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA): CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA): CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS,
    (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE): CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS,
}


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


def normalize_sbm_arrow_table(
    table: pa.Table,
    risk_class: SbmRiskClass | str,
    measure: SbmRiskMeasure | str,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an SBM Arrow table through the canonical path registry.

    Parameters
    ----------
    table
        Raw Arrow table for one homogeneous SBM path.
    risk_class
        Expected SBM risk class.
    measure
        Expected SBM risk measure.
    diagnostics
        Adapter diagnostics to attach.
    metadata
        Optional handoff metadata.
    rejected
        Optional rejected-row table.
    source_hash
        Optional source payload hash.

    Returns
    -------
    NormalizedArrowTable
    """

    return normalize_arrow_table(
        table,
        column_specs=_arrow_column_specs_for_path(risk_class, measure),
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
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
    input_hash = sbm_arrow_columnar_input_hash(table, column_specs)
    kwargs: dict[str, Any] = dict(builder_kwargs or {})
    kwargs.update(_sbm_batch_column_kwargs(columns, row_count=table.num_rows))
    kwargs.update(
        {
            "source_hash": handoff.source_hash,
            "handoff_hash": normalized_arrow_table_hash(handoff),
            "diagnostics": _diagnostics(handoff),
            "input_hash": input_hash,
            "input_hash_algorithm": INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2,
            "copy_arrays": False,
        }
    )
    return build_batch(**kwargs)


def build_sbm_batch_from_arrow(
    handoff: NormalizedArrowTable,
    risk_class: SbmRiskClass | str,
    measure: SbmRiskMeasure | str,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmSensitivityBatch:
    """Build an SBM batch from Arrow through the canonical path registry.

    Parameters
    ----------
    handoff
        Normalized Arrow table for one homogeneous SBM path.
    risk_class
        Expected SBM risk class.
    measure
        Expected SBM risk measure.
    context
        Optional calculation context shape check. Scope filtering remains a
        capital-stage concern.

    Returns
    -------
    SbmSensitivityBatch
    """

    expected_risk_class = coerce_risk_class(risk_class)
    expected_risk_measure = coerce_risk_measure(measure)
    sbm_batch_spec(expected_risk_class, expected_risk_measure)
    if context is not None and not isinstance(context, SbmCalculationContext):
        raise SbmInputError(
            "calculation context must be SbmCalculationContext",
            field="context",
        )
    return _build_sbm_batch_from_arrow(
        handoff,
        column_specs=_arrow_column_specs_for_path(expected_risk_class, expected_risk_measure),
        build_batch=build_sbm_batch_from_columns,
        builder_kwargs={
            "expected_risk_class": expected_risk_class,
            "expected_risk_measure": expected_risk_measure,
        },
    )


def calculate_sbm_capital_from_arrow(
    handoff: NormalizedArrowTable,
    risk_class: SbmRiskClass | str,
    measure: SbmRiskMeasure | str,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital from Arrow through the canonical path registry.

    Parameters
    ----------
    handoff
        Normalized Arrow table for one homogeneous SBM path.
    risk_class
        Expected SBM risk class.
    measure
        Expected SBM risk measure.
    context
        Calculation context for supported profile and scope validation.

    Returns
    -------
    SbmCapitalResult
    """

    batch = build_sbm_batch_from_arrow(
        handoff,
        risk_class,
        measure,
        context=context,
    )
    return calculate_sbm_capital_from_batch(batch, context=context)


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
    return build_sbm_batch_from_arrow(handoff, path[0], path[1])


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


def _arrow_column_specs_for_path(
    risk_class: SbmRiskClass | str,
    measure: SbmRiskMeasure | str,
) -> tuple[ColumnSpec, ...]:
    expected_risk_class = coerce_risk_class(risk_class)
    expected_risk_measure = coerce_risk_measure(measure)
    sbm_batch_spec(expected_risk_class, expected_risk_measure)
    return _ARROW_COLUMN_SPECS_BY_PATH[(expected_risk_class, expected_risk_measure)]


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
    "build_sbm_batch_from_arrow",
    "calculate_sbm_capital_from_arrow",
    "calculate_sbm_portfolio_capital_from_arrow_tables",
    "normalize_sbm_arrow_table",
]
