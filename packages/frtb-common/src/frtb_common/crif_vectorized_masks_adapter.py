"""Vectorized CRIF boolean masks and RiskType key helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]


def _source_row_id_array(values: pa.Array | None, row_count: int) -> pa.Array:
    fallback = pc.cast(pa.array(range(row_count), type=pa.int64()), pa.string())
    if values is None:
        return cast(pa.Array, fallback)
    trimmed = pc.utf8_trim_whitespace(pc.cast(values, pa.string()))
    has_text = _mask_not(_empty_text_mask(cast(pa.Array, trimmed)))
    return cast(pa.Array, pc.if_else(has_text, trimmed, fallback))


def _normalise_risk_type_array(values: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.utf8_upper(_filled_text(pc.utf8_trim_whitespace(values))))


def _supported_risk_type_mask(
    risk_type_keys: pa.Array,
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    row_count: int,
) -> pa.Array:
    if not risk_mapping_by_type:
        return _mask_not(_empty_text_mask(risk_type_keys))
    return cast(
        pa.Array,
        pc.is_in(risk_type_keys, value_set=pa.array(sorted(risk_mapping_by_type))),
    )


def _unsupported_risk_type_messages(
    risk_type_keys: pa.Array,
    unsupported_mask: pa.Array,
) -> Mapping[int, str]:
    indices = _true_indices(unsupported_mask)
    if not indices:
        return {}
    values = risk_type_keys.take(pa.array(indices, type=pa.int64()))
    return {
        index: f"unsupported CRIF RiskType {cast(str, values[offset].as_py())!r}"
        for offset, index in enumerate(indices)
    }


def _filled_text(values: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.fill_null(values, ""))


def _empty_text_mask(values: pa.Array) -> pa.Array:
    filled = _filled_text(values)
    return _mask_or(pc.is_null(values), pc.equal(filled, ""))


def _bool_array(value: bool, row_count: int) -> pa.Array:
    return cast(pa.Array, pa.repeat(pa.scalar(value, type=pa.bool_()), row_count))


def _mask_and(left: pa.Array, right: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.and_(pc.fill_null(left, False), pc.fill_null(right, False)))


def _mask_or(left: pa.Array, right: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.or_(pc.fill_null(left, False), pc.fill_null(right, False)))


def _mask_not(mask: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.invert(pc.fill_null(mask, False)))


def _true_indices(mask: pa.Array) -> tuple[int, ...]:
    indices = pc.indices_nonzero(pc.fill_null(mask, False)).to_numpy(zero_copy_only=False)
    return tuple(indices.tolist())
