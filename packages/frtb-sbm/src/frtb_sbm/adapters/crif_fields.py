"""Field extraction helpers for SBM CRIF row adapters."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import cast

from frtb_sbm.adapters.crif_constants import _SOURCE_ROW_ID_FIELDS
from frtb_sbm.adapters.crif_models import SbmRejectedRow
from frtb_sbm.validation import SbmInputError


def _rejected_row_from_exception(
    record: Mapping[str, object],
    exc: Exception,
    *,
    fallback_row_id: str,
) -> SbmRejectedRow:
    return SbmRejectedRow(
        source_row_id=_first_text(record, _SOURCE_ROW_ID_FIELDS, fallback=fallback_row_id),
        reason=str(exc),
        field=getattr(exc, "field", "") or "RiskType",
        source_row=_source_row_snapshot(record),
    )


def _source_row_snapshot(record: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in record.items()))


def _first_text(
    record: Mapping[str, object],
    fields: tuple[str, ...],
    *,
    fallback: str = "",
) -> str:
    value, _source = _first_text_with_source(record, fields, fallback=fallback)
    return value


def _first_text_with_source(
    record: Mapping[str, object],
    fields: tuple[str, ...],
    *,
    fallback: str = "",
) -> tuple[str, str | None]:
    for field in fields:
        if field in record and record[field] is not None:
            value = str(record[field]).strip()
            if value:
                return value, field
    if fallback:
        return fallback, None
    raise SbmInputError(f"missing required field; tried {fields}", field=fields[0])


def _optional_text_with_source(
    record: Mapping[str, object],
    fields: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for field in fields:
        if field in record and record[field] is not None:
            value = str(record[field]).strip()
            if value:
                return value, field
    return None, None


def _first_float_with_source(
    record: Mapping[str, object],
    fields: tuple[str, ...],
) -> tuple[float, str]:
    for field in fields:
        if field not in record or record[field] is None:
            continue
        try:
            raw_value = record[field]
            if isinstance(raw_value, bool):
                raise ValueError("boolean values are not numeric CRIF amounts")
            value = float(cast(str | float | int, raw_value))
            if not math.isfinite(value):
                raise ValueError("value must be finite")
            return value, field
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                f"field {field} must be numeric and finite",
                field=field,
            ) from exc
    raise SbmInputError(f"missing required numeric field; tried {fields}", field=fields[0])


def _append_column_map(
    column_map: list[tuple[str, str]],
    source_field: str | None,
    canonical_field: str,
) -> None:
    if source_field is None:
        return
    pair = (source_field, canonical_field)
    if pair not in column_map:
        column_map.append(pair)
