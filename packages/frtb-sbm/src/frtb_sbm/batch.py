"""Package-owned sensitivity batches for high-volume SBM kernels.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 and MAR21.39-MAR21.42 — GIRR delta weighting,
    factor netting, and aggregation.
    SBM-NFR-001, SBM-NFR-002, SBM-AUDIT-001.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from frtb_sbm.audit import _hash_payload
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
)
from frtb_sbm.validation import (
    SbmInputError,
    coerce_risk_class,
    coerce_risk_measure,
    coerce_sign_convention,
    normalise_currency_code,
    normalise_sensitivity_amount,
    validate_sbm_sensitivities,
)

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class SbmSensitivityBatch:
    """
    Kernel-facing SBM sensitivity batch.

    The hot fields are immutable NumPy arrays. Non-array metadata is lineage and
    adapter evidence only; kernels must not require Arrow or row dataclasses.
    """

    sensitivity_ids: ObjectArray
    source_row_ids: ObjectArray
    desk_ids: ObjectArray
    legal_entities: ObjectArray
    risk_classes: ObjectArray
    risk_measures: ObjectArray
    buckets: ObjectArray
    risk_factors: ObjectArray
    amounts: FloatArray
    amount_currencies: ObjectArray
    sign_conventions: ObjectArray
    tenors: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    input_hash: str
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()
    position_ids: ObjectArray | None = None
    qualifiers: ObjectArray | None = None
    option_tenors: ObjectArray | None = None
    liquidity_horizon_days: ObjectArray | None = None
    maturities: ObjectArray | None = None
    up_shock_amounts: ObjectArray | None = None
    down_shock_amounts: ObjectArray | None = None
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None

    @property
    def row_count(self) -> int:
        """Return the number of accepted sensitivity rows represented."""

        return int(self.amounts.shape[0])

    @property
    def risk_class(self) -> SbmRiskClass:
        """Return the homogeneous risk class represented by this batch."""

        return SbmRiskClass.GIRR

    @property
    def risk_measure(self) -> SbmRiskMeasure:
        """Return the homogeneous risk measure represented by this batch."""

        return SbmRiskMeasure.DELTA


def build_girr_delta_batch_from_sensitivities(
    sensitivities: object,
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SbmSensitivityBatch:
    """
    Build a GIRR delta batch from existing row-wise canonical sensitivities.

    This compatibility builder is intentionally outside the high-volume Arrow
    path: it starts from already-materialised ``SbmSensitivity`` rows, then
    converts them to the same batch representation used by Arrow handoffs.
    """

    validated = validate_sbm_sensitivities(sensitivities)
    _require_non_empty(validated)
    for sensitivity in validated:
        _require_girr_delta_sensitivity(sensitivity)

    optional_arrays = _optional_arrays_from_sensitivities(validated)
    source_column_maps = _source_column_maps_from_sensitivities(validated)
    mapping_citations = _mapping_citations_from_sensitivities(validated)
    return build_girr_delta_batch_from_columns(
        sensitivity_ids=[item.sensitivity_id for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        desk_ids=[item.desk_id for item in validated],
        legal_entities=[item.legal_entity for item in validated],
        risk_classes=[item.risk_class.value for item in validated],
        risk_measures=[item.risk_measure.value for item in validated],
        buckets=[item.bucket for item in validated],
        risk_factors=[item.risk_factor for item in validated],
        amounts=[item.amount for item in validated],
        amount_currencies=[item.amount_currency for item in validated],
        sign_conventions=[item.sign_convention.value for item in validated],
        tenors=[item.tenor or "" for item in validated],
        lineage_source_systems=[item.lineage.source_system for item in validated],
        lineage_source_files=[item.lineage.source_file for item in validated],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citations,
        copy_arrays=True,
        **optional_arrays,
    )


def build_girr_delta_batch_from_columns(
    *,
    sensitivity_ids: Iterable[object],
    source_row_ids: Iterable[object],
    desk_ids: Iterable[object],
    legal_entities: Iterable[object],
    risk_classes: Iterable[object],
    risk_measures: Iterable[object],
    buckets: Iterable[object],
    risk_factors: Iterable[object],
    amounts: Iterable[object],
    amount_currencies: Iterable[object],
    sign_conventions: Iterable[object],
    tenors: Iterable[object],
    lineage_source_systems: Iterable[object],
    lineage_source_files: Iterable[object],
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    position_ids: Iterable[object] | None = None,
    qualifiers: Iterable[object] | None = None,
    option_tenors: Iterable[object] | None = None,
    liquidity_horizon_days: Iterable[object] | None = None,
    maturities: Iterable[object] | None = None,
    up_shock_amounts: Iterable[object] | None = None,
    down_shock_amounts: Iterable[object] | None = None,
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None = None,
    copy_arrays: bool = True,
) -> SbmSensitivityBatch:
    """Build a GIRR delta batch from columnar arrays owned by an adapter."""

    arrays = {
        "sensitivity_ids": _object_array(sensitivity_ids, "sensitivity_id", copy=copy_arrays),
        "source_row_ids": _object_array(source_row_ids, "source_row_id", copy=copy_arrays),
        "desk_ids": _object_array(desk_ids, "desk_id", copy=copy_arrays),
        "legal_entities": _object_array(legal_entities, "legal_entity", copy=copy_arrays),
        "risk_classes": _object_array(risk_classes, "risk_class", copy=copy_arrays),
        "risk_measures": _object_array(risk_measures, "risk_measure", copy=copy_arrays),
        "buckets": _object_array(buckets, "bucket", copy=copy_arrays),
        "risk_factors": _object_array(risk_factors, "risk_factor", copy=copy_arrays),
        "amount_currencies": _object_array(
            amount_currencies,
            "amount_currency",
            copy=copy_arrays,
        ),
        "sign_conventions": _object_array(
            sign_conventions,
            "sign_convention",
            copy=copy_arrays,
        ),
        "tenors": _object_array(tenors, "tenor", copy=copy_arrays),
        "lineage_source_systems": _object_array(
            lineage_source_systems,
            "lineage_source_system",
            copy=copy_arrays,
        ),
        "lineage_source_files": _object_array(
            lineage_source_files,
            "lineage_source_file",
            copy=copy_arrays,
        ),
    }
    amount_array = _float_array(amounts, "amount", copy=copy_arrays)
    row_count = int(amount_array.shape[0])
    _require_common_length(row_count, arrays)
    _require_non_empty_length(row_count)

    optional = {
        "position_ids": _optional_object_array(position_ids, "position_id", row_count, copy_arrays),
        "qualifiers": _optional_object_array(qualifiers, "qualifier", row_count, copy_arrays),
        "option_tenors": _optional_object_array(
            option_tenors,
            "option_tenor",
            row_count,
            copy_arrays,
        ),
        "liquidity_horizon_days": _optional_object_array(
            liquidity_horizon_days,
            "liquidity_horizon_days",
            row_count,
            copy_arrays,
        ),
        "maturities": _optional_object_array(maturities, "maturity", row_count, copy_arrays),
        "up_shock_amounts": _optional_object_array(
            up_shock_amounts,
            "up_shock_amount",
            row_count,
            copy_arrays,
        ),
        "down_shock_amounts": _optional_object_array(
            down_shock_amounts,
            "down_shock_amount",
            row_count,
            copy_arrays,
        ),
    }

    _validate_source_column_maps(source_column_maps, row_count)
    _validate_mapping_citations(mapping_citation_ids, row_count)
    _validate_girr_delta_batch_arrays(arrays, amount_array)
    diagnostic_payloads = tuple(MappingProxyType(dict(item)) for item in diagnostics)
    batch_without_hash = SbmSensitivityBatch(
        sensitivity_ids=arrays["sensitivity_ids"],
        source_row_ids=arrays["source_row_ids"],
        desk_ids=arrays["desk_ids"],
        legal_entities=arrays["legal_entities"],
        risk_classes=arrays["risk_classes"],
        risk_measures=arrays["risk_measures"],
        buckets=arrays["buckets"],
        risk_factors=arrays["risk_factors"],
        amounts=amount_array,
        amount_currencies=arrays["amount_currencies"],
        sign_conventions=arrays["sign_conventions"],
        tenors=arrays["tenors"],
        lineage_source_systems=arrays["lineage_source_systems"],
        lineage_source_files=arrays["lineage_source_files"],
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostic_payloads,
        source_column_maps=source_column_maps,
        mapping_citation_ids=mapping_citation_ids,
        **optional,
    )
    return replace(
        batch_without_hash, input_hash=input_hash_for_girr_delta_batch(batch_without_hash)
    )


def input_hash_for_girr_delta_batch(batch: SbmSensitivityBatch) -> str:
    """Return the row-equivalent deterministic input hash for a GIRR delta batch."""

    return _hash_payload({"sensitivities": list(_sensitivity_payloads_from_batch(batch))})


def sorted_girr_delta_batch_indices(batch: SbmSensitivityBatch) -> npt.NDArray[np.int64]:
    """Return indices in the same stable order used by row-wise GIRR delta weighting."""

    return np.lexsort(
        (
            batch.sensitivity_ids,
            batch.risk_factors,
            batch.buckets,
            batch.risk_measures,
            batch.risk_classes,
        )
    )


def _optional_arrays_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> dict[str, Iterable[object] | None]:
    optional_fields = {
        "position_ids": tuple(item.position_id for item in sensitivities),
        "qualifiers": tuple(item.qualifier for item in sensitivities),
        "option_tenors": tuple(item.option_tenor for item in sensitivities),
        "liquidity_horizon_days": tuple(item.liquidity_horizon_days for item in sensitivities),
        "maturities": tuple(item.maturity for item in sensitivities),
        "up_shock_amounts": tuple(item.up_shock_amount for item in sensitivities),
        "down_shock_amounts": tuple(item.down_shock_amount for item in sensitivities),
    }
    return {
        field_name: values if any(value is not None for value in values) else None
        for field_name, values in optional_fields.items()
    }


def _source_column_maps_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> tuple[tuple[tuple[str, str], ...], ...] | None:
    source_column_maps = tuple(item.lineage.source_column_map for item in sensitivities)
    if not any(source_column_maps):
        return None
    return source_column_maps


def _mapping_citations_from_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> tuple[tuple[str, ...], ...] | None:
    mapping_citations = tuple(item.mapping_citation_ids for item in sensitivities)
    if not any(mapping_citations):
        return None
    return mapping_citations


def _sensitivity_payloads_from_batch(batch: SbmSensitivityBatch) -> Iterable[dict[str, object]]:
    for row_index in range(batch.row_count):
        sensitivity_id = _str_at(batch.sensitivity_ids, row_index)
        source_row_id = _str_at(batch.source_row_ids, row_index)
        payload: dict[str, object] = {
            "sensitivity_id": sensitivity_id,
            "source_row_id": source_row_id,
            "desk_id": _str_at(batch.desk_ids, row_index),
            "legal_entity": _str_at(batch.legal_entities, row_index),
            "risk_class": _str_at(batch.risk_classes, row_index),
            "risk_measure": _str_at(batch.risk_measures, row_index),
            "bucket": _str_at(batch.buckets, row_index),
            "risk_factor": _str_at(batch.risk_factors, row_index),
            "amount": float(batch.amounts[row_index]),
            "amount_currency": _str_at(batch.amount_currencies, row_index),
            "sign_convention": _str_at(batch.sign_conventions, row_index),
            "lineage": {
                "source_system": _str_at(batch.lineage_source_systems, row_index),
                "source_file": _str_at(batch.lineage_source_files, row_index),
                "source_row_id": source_row_id,
                "source_column_map": [
                    list(pair) for pair in _source_column_map_at(batch, row_index)
                ],
            },
            "mapping_citation_ids": list(_mapping_citation_ids_at(batch, row_index)),
        }
        _add_optional_payload_field(payload, "position_id", batch.position_ids, row_index)
        _add_optional_payload_field(payload, "qualifier", batch.qualifiers, row_index)
        _add_optional_payload_field(payload, "tenor", batch.tenors, row_index)
        _add_optional_payload_field(payload, "option_tenor", batch.option_tenors, row_index)
        _add_optional_payload_field(
            payload,
            "liquidity_horizon_days",
            batch.liquidity_horizon_days,
            row_index,
        )
        _add_optional_payload_field(payload, "maturity", batch.maturities, row_index)
        _add_optional_payload_field(payload, "up_shock_amount", batch.up_shock_amounts, row_index)
        _add_optional_payload_field(
            payload,
            "down_shock_amount",
            batch.down_shock_amounts,
            row_index,
        )
        yield payload


def _add_optional_payload_field(
    payload: dict[str, object],
    field_name: str,
    values: ObjectArray | None,
    row_index: int,
) -> None:
    if values is None:
        return
    value = values[row_index]
    if value is None:
        return
    if field_name in {"liquidity_horizon_days"}:
        payload[field_name] = int(value)
    elif field_name in {"up_shock_amount", "down_shock_amount"}:
        payload[field_name] = float(value)
    else:
        payload[field_name] = cast(str, value)


def _source_column_map_at(
    batch: SbmSensitivityBatch,
    row_index: int,
) -> tuple[tuple[str, str], ...]:
    if batch.source_column_maps is None:
        return ()
    return batch.source_column_maps[row_index]


def _mapping_citation_ids_at(batch: SbmSensitivityBatch, row_index: int) -> tuple[str, ...]:
    if batch.mapping_citation_ids is None:
        return ()
    return batch.mapping_citation_ids[row_index]


def _validate_girr_delta_batch_arrays(
    arrays: Mapping[str, ObjectArray],
    amount_array: FloatArray,
) -> None:
    seen_ids: set[str] = set()
    for row_index in range(int(amount_array.shape[0])):
        sensitivity_id = _require_text_array_value(
            arrays["sensitivity_ids"],
            row_index,
            "sensitivity_id",
        )
        if sensitivity_id in seen_ids:
            raise SbmInputError(
                "duplicate sensitivity id",
                field="sensitivity_id",
                sensitivity_id=sensitivity_id,
            )
        seen_ids.add(sensitivity_id)
        _require_text_array_value(arrays["source_row_ids"], row_index, "source_row_id")
        _require_text_array_value(arrays["desk_ids"], row_index, "desk_id", sensitivity_id)
        _require_text_array_value(
            arrays["legal_entities"],
            row_index,
            "legal_entity",
            sensitivity_id,
        )
        _require_text_array_value(arrays["buckets"], row_index, "bucket", sensitivity_id)
        _require_text_array_value(
            arrays["risk_factors"],
            row_index,
            "risk_factor",
            sensitivity_id,
        )
        _require_text_array_value(arrays["tenors"], row_index, "tenor", sensitivity_id)
        _require_text_array_value(
            arrays["lineage_source_systems"],
            row_index,
            "lineage.source_system",
            sensitivity_id,
        )
        _require_text_array_value(
            arrays["lineage_source_files"],
            row_index,
            "lineage.source_file",
            sensitivity_id,
        )
        risk_class = coerce_risk_class(arrays["risk_classes"][row_index])
        risk_measure = coerce_risk_measure(arrays["risk_measures"][row_index])
        if risk_class is not SbmRiskClass.GIRR:
            raise SbmInputError(
                "GIRR delta batch only accepts GIRR sensitivities",
                field="risk_class",
                sensitivity_id=sensitivity_id,
            )
        if risk_measure is not SbmRiskMeasure.DELTA:
            raise SbmInputError(
                "GIRR delta batch only accepts delta sensitivities",
                field="risk_measure",
                sensitivity_id=sensitivity_id,
            )
        normalise_currency_code(
            cast(str, arrays["amount_currencies"][row_index]),
            sensitivity_id=sensitivity_id,
        )
        coerce_sign_convention(arrays["sign_conventions"][row_index])
        normalise_sensitivity_amount(float(amount_array[row_index]), sensitivity_id=sensitivity_id)


def _validate_source_column_maps(
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...] | None,
    row_count: int,
) -> None:
    if source_column_maps is None:
        return
    if len(source_column_maps) != row_count:
        raise SbmInputError(
            "source_column_maps length must match batch row count",
            field="lineage.source_column_map",
        )
    for row_map in source_column_maps:
        for source_field, canonical_field in row_map:
            if not isinstance(source_field, str) or not source_field.strip():
                raise SbmInputError(
                    "source column map entries require non-empty source fields",
                    field="lineage.source_column_map",
                )
            if not isinstance(canonical_field, str) or not canonical_field.strip():
                raise SbmInputError(
                    "source column map entries require non-empty canonical fields",
                    field="lineage.source_column_map",
                )


def _validate_mapping_citations(
    mapping_citation_ids: tuple[tuple[str, ...], ...] | None,
    row_count: int,
) -> None:
    if mapping_citation_ids is None:
        return
    if len(mapping_citation_ids) != row_count:
        raise SbmInputError(
            "mapping_citation_ids length must match batch row count",
            field="mapping_citation_ids",
        )
    for row_citations in mapping_citation_ids:
        for citation_id in row_citations:
            if not isinstance(citation_id, str) or not citation_id.strip():
                raise SbmInputError(
                    "mapping citation ids must be non-empty strings",
                    field="mapping_citation_ids",
                )


def _object_array(values: Iterable[object], field: str, *, copy: bool) -> ObjectArray:
    if isinstance(values, np.ndarray):
        array = values.astype(object, copy=copy)
    else:
        array = np.asarray(tuple(values), dtype=object)
    if array.ndim != 1:
        raise SbmInputError("column arrays must be one-dimensional", field=field)
    _freeze_array(array)
    return cast(ObjectArray, array)


def _float_array(values: Iterable[object], field: str, *, copy: bool) -> FloatArray:
    try:
        if isinstance(values, np.ndarray):
            array = values.astype(np.float64, copy=copy)
        else:
            array = np.asarray(tuple(values), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SbmInputError("value must be numeric", field=field) from exc
    if array.ndim != 1:
        raise SbmInputError("column arrays must be one-dimensional", field=field)
    if not np.all(np.isfinite(array)):
        raise SbmInputError("value must be finite", field=field)
    _freeze_array(array)
    return cast(FloatArray, array)


def _optional_object_array(
    values: Iterable[object] | None,
    field: str,
    row_count: int,
    copy: bool,
) -> ObjectArray | None:
    if values is None:
        return None
    array = _object_array(values, field, copy=copy)
    if int(array.shape[0]) != row_count:
        raise SbmInputError(f"{field} length must match batch row count", field=field)
    if not any(value is not None for value in array):
        return None
    return array


def _require_common_length(row_count: int, arrays: Mapping[str, ObjectArray]) -> None:
    for field_name, array in arrays.items():
        if int(array.shape[0]) != row_count:
            raise SbmInputError(
                f"{field_name} length must match amount length",
                field=field_name,
            )


def _require_non_empty(values: Sequence[SbmSensitivity]) -> None:
    _require_non_empty_length(len(values))


def _require_non_empty_length(row_count: int) -> None:
    if row_count == 0:
        raise SbmInputError("GIRR delta batch must not be empty", field="sensitivities")


def _require_girr_delta_sensitivity(sensitivity: SbmSensitivity) -> None:
    if sensitivity.risk_class is not SbmRiskClass.GIRR:
        raise SbmInputError(
            "GIRR delta batch only accepts GIRR sensitivities",
            field="risk_class",
            sensitivity_id=sensitivity.sensitivity_id,
        )
    if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
        raise SbmInputError(
            "GIRR delta batch only accepts delta sensitivities",
            field="risk_measure",
            sensitivity_id=sensitivity.sensitivity_id,
        )


def _require_text_array_value(
    values: ObjectArray,
    row_index: int,
    field: str,
    sensitivity_id: str = "",
) -> str:
    value = values[row_index]
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError(
            "non-empty text is required",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value


def _str_at(values: ObjectArray, row_index: int) -> str:
    return cast(str, values[row_index])


def _freeze_array(array: npt.NDArray[Any]) -> None:
    array.setflags(write=False)


__all__ = [
    "SbmSensitivityBatch",
    "build_girr_delta_batch_from_columns",
    "build_girr_delta_batch_from_sensitivities",
    "input_hash_for_girr_delta_batch",
    "sorted_girr_delta_batch_indices",
]
