"""Arrow-to-RRAO batch column materialization helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
import numpy.typing as npt

from frtb_rrao.assembly.hashes import INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2
from frtb_rrao.batch import RraoPositionBatch

ArrowColumnArray = npt.NDArray[Any]
ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]


def _batch_from_arrow_columns(
    columns: Mapping[str, ArrowColumnArray],
    *,
    row_count: int,
    source_hash: str | None,
    handoff_hash: str,
    diagnostics: Sequence[Mapping[str, object]],
    input_hash: str,
) -> RraoPositionBatch:
    field_values = {
        **_identity_columns(columns),
        **_classification_columns(columns, row_count),
        **_shape_columns(columns, row_count),
        **_investment_fund_columns(columns, row_count),
        **_lineage_columns(columns, row_count),
    }
    return RraoPositionBatch(
        **field_values,
        input_hash=input_hash,
        input_hash_algorithm=INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )


def _identity_columns(columns: Mapping[str, ArrowColumnArray]) -> dict[str, object]:
    return {
        "position_ids": _required_text_column(columns, "position_id"),
        "source_row_ids": _required_text_column(columns, "source_row_id"),
        "desk_ids": _required_text_column(columns, "desk_id"),
        "legal_entities": _required_text_column(columns, "legal_entity"),
        "gross_effective_notionals": _float_column(columns, "gross_effective_notional"),
        "currencies": _required_text_column(columns, "currency"),
        "evidence_types": _required_text_column(columns, "evidence_type"),
        "evidence_labels": _required_text_column(columns, "evidence_label"),
    }


def _classification_columns(
    columns: Mapping[str, ArrowColumnArray],
    row_count: int,
) -> dict[str, object]:
    return {
        "classification_hints": _optional_text_column(columns, "classification_hint", row_count),
        "exclusion_reasons": _optional_text_column(columns, "exclusion_reason", row_count),
        "exclusion_evidence_ids": _optional_text_column(
            columns,
            "exclusion_evidence_id",
            row_count,
        ),
        "back_to_back_match_group_ids": _optional_text_column(
            columns,
            "back_to_back_match_group_id",
            row_count,
        ),
        "back_to_back_matched_position_ids": _optional_text_column(
            columns,
            "back_to_back_matched_position_id",
            row_count,
        ),
        "supervisor_directive_ids": _optional_text_column(
            columns,
            "supervisor_directive_id",
            row_count,
        ),
    }


def _shape_columns(
    columns: Mapping[str, ArrowColumnArray],
    row_count: int,
) -> dict[str, object]:
    return {
        "underlying_counts": _optional_object_column(columns, "underlying_count", row_count),
        "is_path_dependents": _optional_object_column(columns, "is_path_dependent", row_count),
        "has_maturities": _optional_object_column(columns, "has_maturity", row_count),
        "has_strike_or_barriers": _optional_object_column(
            columns,
            "has_strike_or_barrier",
            row_count,
        ),
        "has_multiple_strikes_or_barriers": _optional_object_column(
            columns,
            "has_multiple_strikes_or_barriers",
            row_count,
        ),
        "is_ctp_hedges": _bool_column(columns, "is_ctp_hedge", row_count, default=False),
    }


def _investment_fund_columns(
    columns: Mapping[str, ArrowColumnArray],
    row_count: int,
) -> dict[str, object]:
    return {
        "is_investment_fund_exposures": _bool_column(
            columns,
            "is_investment_fund_exposure",
            row_count,
            default=False,
        ),
        "investment_fund_ids": _optional_text_column(columns, "investment_fund_id", row_count),
        "investment_fund_section_205_methods": _optional_text_column(
            columns,
            "investment_fund_section_205_method",
            row_count,
        ),
        "investment_fund_included_exposure_types": _optional_text_column(
            columns,
            "investment_fund_included_exposure_type",
            row_count,
        ),
        "investment_fund_mandate_evidence_ids": _optional_text_column(
            columns,
            "investment_fund_mandate_evidence_id",
            row_count,
        ),
        "investment_fund_section_205_evidence_ids": _optional_text_column(
            columns,
            "investment_fund_section_205_evidence_id",
            row_count,
        ),
        "investment_fund_gross_effective_notionals": _optional_float_column(
            columns,
            "investment_fund_gross_effective_notional",
            row_count,
        ),
        "investment_fund_included_exposure_ratios": _optional_float_column(
            columns,
            "investment_fund_included_exposure_ratio",
            row_count,
        ),
        "investment_fund_look_through_availables": _bool_column(
            columns,
            "investment_fund_look_through_available",
            row_count,
            default=False,
        ),
        "investment_fund_mandate_allows_rrao_exposures": _bool_column(
            columns,
            "investment_fund_mandate_allows_rrao_exposures",
            row_count,
            default=True,
        ),
    }


def _lineage_columns(
    columns: Mapping[str, ArrowColumnArray],
    row_count: int,
) -> dict[str, object]:
    return {
        "notional_sources": _text_column_with_default(
            columns,
            "notional_source",
            row_count,
            default="reported",
        ),
        "lineage_source_systems": _required_text_column(columns, "lineage_source_system"),
        "lineage_source_files": _required_text_column(columns, "lineage_source_file"),
        "lineage_source_row_ids": _lineage_source_row_ids(columns, row_count),
        "lineage_present": _batch_arrays.readonly_array(
            np.ones(row_count, dtype=np.bool_),
            copy=False,
        ),
        "source_column_maps": tuple(() for _ in range(row_count)),
        "citations": _citations_column(columns.get("citations"), row_count),
    }


def _required_text_column(columns: Mapping[str, ArrowColumnArray], name: str) -> ObjectArray:
    values = columns.get(name)
    if values is None:
        from frtb_rrao.validation._errors import RraoInputError

        raise RraoInputError(f"Required column {name!r} is missing", field=name)
    return _required_text_array(values, name)


def _required_text_array(values: ArrowColumnArray, field: str) -> ObjectArray:
    from frtb_rrao.validation._errors import RraoInputError

    result = _optional_text_array(values)
    invalid = result == None  # noqa: E711
    if bool(np.any(invalid)):
        raise RraoInputError("non-empty text is required", field=field)
    return result


def _optional_text_column(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    row_count: int,
) -> ObjectArray:
    values = columns.get(name)
    if values is None:
        return _object_default(None, row_count)
    return _optional_text_array(values)


def _text_column_with_default(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    row_count: int,
    *,
    default: str,
) -> ObjectArray:
    values = columns.get(name)
    if values is None:
        return _object_default(default, row_count)
    result = np.asarray(values, dtype=object).copy()
    for index, value in enumerate(result):
        text = None if value is None else str(value).strip()
        result[index] = text or default
    result.setflags(write=False)
    return cast(ObjectArray, result)


def _lineage_source_row_ids(
    columns: Mapping[str, ArrowColumnArray],
    row_count: int,
) -> ObjectArray:
    values = columns.get("lineage_source_row_id")
    if values is None:
        return _required_text_column(columns, "source_row_id")
    return _optional_text_column(columns, "lineage_source_row_id", row_count)


def _optional_object_column(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    row_count: int,
) -> ObjectArray:
    values = columns.get(name)
    if values is None:
        return _object_default(None, row_count)
    return _batch_arrays.object_array(values, copy=False)


def _float_column(columns: Mapping[str, ArrowColumnArray], name: str) -> FloatArray:
    values = columns.get(name)
    if values is None:
        from frtb_rrao.validation._errors import RraoInputError

        raise RraoInputError(f"Required column {name!r} is missing", field=name)
    return _batch_arrays.readonly_array(np.asarray(values, dtype=np.float64), copy=False)


def _optional_float_column(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    row_count: int,
) -> FloatArray:
    values = columns.get(name)
    if values is None:
        return _batch_arrays.readonly_array(
            np.full(row_count, np.nan, dtype=np.float64),
            copy=False,
        )
    return _batch_arrays.readonly_array(np.asarray(values, dtype=np.float64), copy=False)


def _bool_column(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    row_count: int,
    *,
    default: bool,
) -> BoolArray:
    values = columns.get(name)
    if values is None:
        return _batch_arrays.readonly_array(
            np.full(row_count, default, dtype=np.bool_),
            copy=False,
        )
    return _batch_arrays.readonly_array(np.asarray(values, dtype=np.bool_), copy=False)


def _optional_text_array(values: ArrowColumnArray) -> ObjectArray:
    result = np.asarray(values, dtype=object).copy()
    for index, value in enumerate(result):
        if value is None:
            continue
        text = str(value).strip()
        result[index] = text or None
    result.setflags(write=False)
    return cast(ObjectArray, result)


def _object_default(value: object, row_count: int) -> ObjectArray:
    return _batch_arrays.object_array([value] * row_count, copy=False)


def _citations_column(
    values: ArrowColumnArray | None,
    row_count: int,
) -> tuple[tuple[str, ...], ...]:
    if values is None:
        return tuple(() for _ in range(row_count))
    groups: list[tuple[str, ...]] = []
    for value in values:
        if value is None or not str(value).strip():
            groups.append(())
            continue
        groups.append(tuple(item.strip() for item in str(value).split(",") if item.strip()))
    return tuple(groups)
