"""SA-CVA sensitivity column adapter for CVA batch contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from frtb_cva._batch_columns import (
    ColumnInput,
    NullableColumnInput,
    _bool_array,
    _default_text_sequence,
    _enum_array,
    _float_array,
    _freeze_source_column_maps,
    _optional_enum_array,
    _optional_float_array,
    _optional_text_array,
    _require_lengths,
    _require_optional_lengths,
    _required_text_array,
)
from frtb_cva._batch_contracts import (
    SaCvaSensitivityBatch,
)
from frtb_cva.data_models import (
    CvaSector,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SensitivityTag,
)
from frtb_cva.validation import (
    CvaInputError,
)
from frtb_cva.validation.batches import (
    _validate_sensitivity_batch,
)


def build_sa_cva_sensitivity_batch_from_columns(
    *,
    sensitivity_ids: ColumnInput,
    risk_classes: ColumnInput,
    risk_measures: ColumnInput,
    sensitivity_tags: ColumnInput,
    bucket_ids: ColumnInput,
    risk_factor_keys: ColumnInput,
    amounts: ColumnInput,
    amount_currencies: ColumnInput,
    sign_conventions: ColumnInput,
    source_row_ids: ColumnInput,
    tenors: NullableColumnInput | None = None,
    volatility_inputs: NullableColumnInput | None = None,
    hedge_ids: NullableColumnInput | None = None,
    index_treatments: NullableColumnInput | None = None,
    index_max_sector_weights: NullableColumnInput | None = None,
    index_homogeneous_sector_quality: ColumnInput | None = None,
    index_dominant_sectors: NullableColumnInput | None = None,
    index_remap_bucket_ids: NullableColumnInput | None = None,
    volatility_surface_ids: NullableColumnInput | None = None,
    volatility_surface_point_ids: NullableColumnInput | None = None,
    shock_ids: NullableColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> SaCvaSensitivityBatch:
    """Build a validated SA-CVA sensitivity batch from aligned column inputs.

    Parameters
    ----------
    sensitivity_ids : ColumnInput
        First required column; remaining inputs are aligned columns or options.

    Returns
    -------
    SaCvaSensitivityBatch
        Validated immutable batch contract for downstream SA-CVA calculation.
    """
    row_count = len(sensitivity_ids)
    if row_count == 0:
        raise CvaInputError("sensitivity batch requires at least one row", field="sensitivities")
    _require_sensitivity_lengths(
        row_count,
        required={
            "risk_classes": risk_classes,
            "risk_measures": risk_measures,
            "sensitivity_tags": sensitivity_tags,
            "bucket_ids": bucket_ids,
            "risk_factor_keys": risk_factor_keys,
            "amounts": amounts,
            "amount_currencies": amount_currencies,
            "sign_conventions": sign_conventions,
            "source_row_ids": source_row_ids,
        },
        optional={
            "tenors": tenors,
            "volatility_inputs": volatility_inputs,
            "hedge_ids": hedge_ids,
            "index_treatments": index_treatments,
            "index_max_sector_weights": index_max_sector_weights,
            "index_homogeneous_sector_quality": index_homogeneous_sector_quality,
            "index_dominant_sectors": index_dominant_sectors,
            "index_remap_bucket_ids": index_remap_bucket_ids,
            "volatility_surface_ids": volatility_surface_ids,
            "volatility_surface_point_ids": volatility_surface_point_ids,
            "shock_ids": shock_ids,
            "lineage_source_systems": lineage_source_systems,
            "lineage_source_files": lineage_source_files,
            "lineage_source_row_ids": lineage_source_row_ids,
            "source_column_maps": source_column_maps,
        },
    )
    batch = SaCvaSensitivityBatch(
        **_sensitivity_batch_fields(
            row_count=row_count,
            source_hash=source_hash,
            handoff_hash=handoff_hash,
            diagnostics=diagnostics,
            copy_arrays=copy_arrays,
            columns=locals(),
        )
    )
    _validate_sensitivity_batch(batch)
    return batch


def _require_sensitivity_lengths(
    row_count: int,
    *,
    required: Mapping[str, ColumnInput],
    optional: Mapping[str, ColumnInput | Sequence[Sequence[tuple[str, str]]] | None],
) -> None:
    _require_lengths(row_count, **required)
    _require_optional_lengths(row_count, **optional)


def _sensitivity_batch_fields(
    *,
    row_count: int,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    fields = _sensitivity_core_fields(row_count=row_count, copy_arrays=copy_arrays, columns=columns)
    fields.update(
        _sensitivity_index_fields(row_count=row_count, copy_arrays=copy_arrays, columns=columns)
    )
    fields.update(
        _sensitivity_lineage_fields(
            row_count=row_count,
            source_hash=source_hash,
            handoff_hash=handoff_hash,
            diagnostics=diagnostics,
            copy_arrays=copy_arrays,
            columns=columns,
        )
    )
    return fields


def _sensitivity_core_fields(
    *,
    row_count: int,
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "sensitivity_ids": _required_text_array(
            columns["sensitivity_ids"], "sensitivity_id", copy=copy_arrays
        ),
        "risk_classes": _enum_array(
            columns["risk_classes"], SaCvaRiskClass, "risk_class", copy=copy_arrays
        ),
        "risk_measures": _enum_array(
            columns["risk_measures"], SaCvaRiskMeasure, "risk_measure", copy=copy_arrays
        ),
        "sensitivity_tags": _enum_array(
            columns["sensitivity_tags"], SensitivityTag, "sensitivity_tag", copy=copy_arrays
        ),
        "bucket_ids": _required_text_array(columns["bucket_ids"], "bucket_id", copy=copy_arrays),
        "risk_factor_keys": _required_text_array(
            columns["risk_factor_keys"], "risk_factor_key", copy=copy_arrays
        ),
        "amounts": _float_array(columns["amounts"], "amount", copy=copy_arrays),
        "amount_currencies": _required_text_array(
            columns["amount_currencies"], "amount_currency", copy=copy_arrays
        ),
        "sign_conventions": _required_text_array(
            columns["sign_conventions"], "sign_convention", copy=copy_arrays
        ),
        "source_row_ids": _required_text_array(
            columns["source_row_ids"], "source_row_id", copy=copy_arrays
        ),
        "tenors": _optional_text_array(columns["tenors"], row_count, copy=copy_arrays),
        "volatility_inputs": _optional_float_array(
            columns["volatility_inputs"], row_count, copy=copy_arrays
        ),
        "hedge_ids": _optional_text_array(columns["hedge_ids"], row_count, copy=copy_arrays),
        "volatility_surface_ids": _optional_text_array(
            columns["volatility_surface_ids"], row_count, copy=copy_arrays
        ),
        "volatility_surface_point_ids": _optional_text_array(
            columns["volatility_surface_point_ids"], row_count, copy=copy_arrays
        ),
        "shock_ids": _optional_text_array(columns["shock_ids"], row_count, copy=copy_arrays),
    }


def _sensitivity_index_fields(
    *,
    row_count: int,
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "index_treatments": _optional_enum_array(
            columns["index_treatments"],
            row_count,
            SaCvaIndexTreatment,
            "index_treatment",
            copy=copy_arrays,
        ),
        "index_max_sector_weights": _optional_float_array(
            columns["index_max_sector_weights"], row_count, copy=copy_arrays
        ),
        "index_homogeneous_sector_quality": _bool_array(
            columns["index_homogeneous_sector_quality"],
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        "index_dominant_sectors": _optional_enum_array(
            columns["index_dominant_sectors"],
            row_count,
            CvaSector,
            "index_dominant_sector",
            copy=copy_arrays,
        ),
        "index_remap_bucket_ids": _optional_text_array(
            columns["index_remap_bucket_ids"], row_count, copy=copy_arrays
        ),
    }


def _sensitivity_lineage_fields(
    *,
    row_count: int,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    source_row_ids = columns["source_row_ids"]
    lineage_source_row_ids = columns["lineage_source_row_ids"]
    return {
        "lineage_source_systems": _required_text_array(
            _default_text_sequence(columns["lineage_source_systems"], row_count, "cva-batch"),
            "lineage.source_system",
            copy=copy_arrays,
        ),
        "lineage_source_files": _required_text_array(
            _default_text_sequence(columns["lineage_source_files"], row_count, "columns"),
            "lineage.source_file",
            copy=copy_arrays,
        ),
        "lineage_source_row_ids": _required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        "source_column_maps": _freeze_source_column_maps(columns["source_column_maps"], row_count),
        "source_hash": source_hash,
        "handoff_hash": handoff_hash,
        "diagnostics": tuple(dict(item) for item in diagnostics),
    }
