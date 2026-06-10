from __future__ import annotations

import numpy as np
import pytest
from frtb_common.batch_arrays import BatchArrayCoercionError

import frtb_rrao._batch_columns as columns
from frtb_rrao.data_models import RraoEvidenceType
from frtb_rrao.validation import RraoInputError


def test_rrao_batch_column_helpers_report_length_and_required_text_errors() -> None:
    with pytest.raises(RraoInputError, match="length does not match"):
        columns._require_lengths(2, desk_ids=["desk-1"])

    with pytest.raises(RraoInputError, match="non-empty text"):
        columns._required_text_array([None], "position_id", copy=True)


def test_rrao_batch_column_helpers_report_sorted_duplicate_position_id() -> None:
    values = np.asarray(["pos-b", "pos-a", "pos-b", "pos-a"], dtype=object)

    with pytest.raises(RraoInputError, match="duplicate position id") as exc_info:
        columns._require_unique(values)

    assert exc_info.value.field == "position_id"
    assert exc_info.value.position_id == "pos-a"


def test_rrao_batch_column_helpers_report_numeric_errors() -> None:
    with pytest.raises(RraoInputError, match="numeric"):
        columns._required_float_array([None], "gross_effective_notional", copy=True)

    with pytest.raises(RraoInputError, match="numeric"):
        columns._required_float_array(["not numeric"], "gross_effective_notional", copy=True)

    with pytest.raises(RraoInputError, match="finite"):
        columns._required_float_array([float("inf")], "gross_effective_notional", copy=True)

    optional = columns._optional_float_array([float("nan"), " "], 2, copy=True)
    assert np.isnan(optional).all()

    with pytest.raises(RraoInputError, match="value must be numeric") as optional_error:
        columns._optional_float_array(["not numeric"], 1, copy=True)
    assert optional_error.value.field == "optional numeric field"


def test_rrao_batch_column_helpers_report_optional_int_and_enum_errors() -> None:
    with pytest.raises(RraoInputError, match="integer"):
        columns._optional_int_array([" ", "not an int"], 2, copy=True)

    with pytest.raises(RraoInputError, match="invalid evidence_type"):
        columns._enum_array(["not-a-type"], RraoEvidenceType, "evidence_type", copy=True)

    optional = columns._optional_enum_array(
        [None, "", "GAP_RISK"],
        3,
        RraoEvidenceType,
        "evidence_type",
        copy=True,
    )
    assert optional.tolist() == [None, None, "GAP_RISK"]


def test_rrao_batch_column_helpers_wrap_common_bool_and_float_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RraoInputError, match="unsupported value"):
        columns._optional_bool_object_array(["maybe"], 1, copy=True)

    def raise_float_error(*args: object, **kwargs: object) -> None:
        raise BatchArrayCoercionError("float conversion failed", field="numeric field")

    monkeypatch.setattr(columns._batch_arrays, "float_array_from_numpy", raise_float_error)
    with pytest.raises(RraoInputError, match="float conversion failed"):
        columns._required_float_array([1.0], "gross_effective_notional", copy=True)


def test_rrao_batch_column_helpers_validate_citations() -> None:
    with pytest.raises(RraoInputError, match="citations"):
        columns._freeze_citations([[object()]], 1)

    with pytest.raises(RraoInputError, match="citations"):
        columns._freeze_citations([[" "]], 1)


def test_rrao_batch_column_helpers_preserve_source_map_validation() -> None:
    result = columns._freeze_source_column_maps([[("raw_b", "canonical_b")]], 1)

    assert result == ((("raw_b", "canonical_b"),),)
    with pytest.raises(RraoInputError, match="non-empty text") as source_error:
        columns._freeze_source_column_maps([[("", "canonical")]], 1)
    assert source_error.value.field == "lineage.source_column_map.source"

    with pytest.raises(RraoInputError, match="non-empty text") as target_error:
        columns._freeze_source_column_maps([[("raw", "")]], 1)
    assert target_error.value.field == "lineage.source_column_map.canonical"
