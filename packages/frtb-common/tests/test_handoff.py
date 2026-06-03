"""Tests for the common Arrow-backed tabular handoff contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pyarrow as pa
import pytest
from frtb_common import (
    DEFAULT_ROW_ID_COLUMN,
    AdapterDiagnostic,
    ChunkPolicy,
    ColumnSpec,
    DictionaryPolicy,
    NormalizedArrowTable,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
    arrow_table_content_hash,
    dictionary_code_chunks,
    dictionary_code_column,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    resolve_column_name,
    sort_table_by_columns,
    source_content_hash,
    validate_arrow_table,
    validate_column_specs,
)


def test_normalize_arrow_table_renames_aliases_and_validates_row_ids() -> None:
    table = pa.table(
        {
            DEFAULT_ROW_ID_COLUMN: ["r1", "r2"],
            "desk": ["rates", "credit"],
            "amount": [1.0, 2.0],
        }
    )
    specs = (
        ColumnSpec(
            name="risk_class",
            aliases=("desk",),
            logical_type=TabularLogicalType.STRING,
        ),
        ColumnSpec(name="amount", logical_type=TabularLogicalType.FLOAT),
    )

    handoff = normalize_arrow_table(
        table,
        column_specs=specs,
        row_id_column=DEFAULT_ROW_ID_COLUMN,
        source_hash=source_content_hash("source-v1"),
        require_unique_row_ids=True,
        metadata={"adapter": "unit-test"},
    )

    assert handoff.accepted.column_names == [DEFAULT_ROW_ID_COLUMN, "risk_class", "amount"]
    assert resolve_column_name(table, specs[0]) == "desk"
    assert handoff.source_hash == source_content_hash("source-v1")
    assert normalized_arrow_table_hash(handoff) == normalized_arrow_table_hash(handoff)


def test_missing_required_column_fails() -> None:
    table = pa.table({"row_id": ["r1"]})

    with pytest.raises(NormalizedTableError, match="Required column 'amount' is missing"):
        normalize_arrow_table(
            table,
            column_specs=(ColumnSpec(name="amount", logical_type=TabularLogicalType.FLOAT),),
        )


def test_duplicate_column_specs_and_aliases_fail() -> None:
    specs = (
        ColumnSpec(name="amount", aliases=("value",)),
        ColumnSpec(name="value", aliases=("raw_value",)),
    )

    with pytest.raises(NormalizedTableError, match="Column identifier 'value'"):
        validate_column_specs(specs)


def test_null_policy_is_explicit() -> None:
    table = pa.table({"amount": pa.array([1.0, None])})
    spec = ColumnSpec(name="amount", null_policy=NullPolicy.FORBID)

    with pytest.raises(NormalizedTableError, match="contains nulls"):
        validate_arrow_table(table, column_specs=(spec,))

    validate_arrow_table(
        table,
        column_specs=(ColumnSpec(name="amount", null_policy=NullPolicy.ALLOW),),
    )


def test_chunk_policy_is_explicit() -> None:
    chunked = pa.chunked_array([pa.array([1.0]), pa.array([2.0])])
    table = pa.table({"amount": chunked})

    with pytest.raises(NormalizedTableError, match="multiple chunks"):
        validate_arrow_table(
            table,
            column_specs=(ColumnSpec(name="amount", chunk_policy=ChunkPolicy.FORBID),),
        )

    validate_arrow_table(
        table,
        column_specs=(ColumnSpec(name="amount", chunk_policy=ChunkPolicy.ALLOW),),
    )


def test_dictionary_policy_and_code_column_are_explicit() -> None:
    dictionary = pa.array(["rates", "credit"])
    indices = pa.array([0, 1, 0], type=pa.int8())
    table = pa.table({"risk_class": pa.DictionaryArray.from_arrays(indices, dictionary)})

    validate_arrow_table(
        table,
        column_specs=(
            ColumnSpec(
                name="risk_class",
                logical_type=TabularLogicalType.DICTIONARY,
                dictionary_policy=DictionaryPolicy.REQUIRE,
            ),
        ),
    )
    code_column = dictionary_code_column(table, "risk_class")

    assert code_column.to_pylist() == [0, 1, 0]
    with pytest.raises(NormalizedTableError, match="dictionary encoded"):
        validate_arrow_table(
            table,
            column_specs=(
                ColumnSpec(name="risk_class", dictionary_policy=DictionaryPolicy.FORBID),
            ),
        )


def test_dictionary_code_chunks_validates_empty_column_type() -> None:
    dictionary_type = pa.dictionary(pa.int8(), pa.string())
    assert dictionary_code_chunks(pa.chunked_array([], type=dictionary_type)) == ()

    with pytest.raises(NormalizedTableError, match="dictionary encoded"):
        dictionary_code_chunks(pa.chunked_array([], type=pa.string()))


def test_metadata_and_handoff_records_are_immutable() -> None:
    handoff = normalize_arrow_table(
        pa.table({"row_id": ["r1"], "amount": [1.0]}),
        column_specs=(ColumnSpec(name="amount"),),
        row_id_column="row_id",
        diagnostics=(AdapterDiagnostic(code="ROW_OK", message="accepted"),),
        metadata={"source": "test"},
    )

    with pytest.raises(FrozenInstanceError):
        handoff.source_hash = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        handoff.metadata["source"] = "changed"  # type: ignore[index]


def test_rejected_rows_and_diagnostics_participate_in_handoff_hash() -> None:
    accepted = pa.table({"row_id": ["r1"], "amount": [1.0]})
    rejected = pa.table({"row_id": ["r2"], "reason": ["bad_amount"]})
    handoff = normalize_arrow_table(
        accepted,
        column_specs=(ColumnSpec(name="amount"),),
        row_id_column="row_id",
        rejected=rejected,
        diagnostics=(
            AdapterDiagnostic(
                code="BAD_AMOUNT",
                message="Amount was rejected",
                row_id="r2",
                column_name="amount",
            ),
        ),
    )

    assert handoff.rejected is rejected
    assert handoff.diagnostics[0].row_id == "r2"
    assert normalized_arrow_table_hash(handoff) != normalized_arrow_table_hash(
        normalize_arrow_table(
            accepted,
            column_specs=(ColumnSpec(name="amount"),),
            row_id_column="row_id",
        )
    )


def test_row_id_uniqueness_is_enforced_when_required() -> None:
    table = pa.table({"row_id": ["r1", "r1"], "amount": [1.0, 2.0]})

    validate_arrow_table(table, row_id_column="row_id", require_unique_row_ids=False)
    with pytest.raises(NormalizedTableError, match="contains duplicates"):
        validate_arrow_table(table, row_id_column="row_id", require_unique_row_ids=True)


def test_arrow_and_handoff_hashes_are_deterministic() -> None:
    table = pa.table({"row_id": ["r2", "r1"], "amount": [2.0, 1.0]})
    sorted_table = sort_table_by_columns(table, ("row_id",))
    handoff = NormalizedArrowTable(
        accepted=sorted_table,
        column_specs=(ColumnSpec(name="amount"),),
        row_id_column="row_id",
        require_unique_row_ids=True,
    )

    assert sorted_table["row_id"].to_pylist() == ["r1", "r2"]
    assert arrow_table_content_hash(sorted_table) == arrow_table_content_hash(sorted_table)
    assert normalized_arrow_table_hash(handoff) == normalized_arrow_table_hash(handoff)


def test_arrow_table_hash_canonicalizes_chunking() -> None:
    single_chunk = pa.table({"row_id": ["r1", "r2"], "amount": [1.0, 2.0]})
    two_chunks = pa.table(
        {
            "row_id": pa.chunked_array([pa.array(["r1"]), pa.array(["r2"])]),
            "amount": pa.chunked_array([pa.array([1.0]), pa.array([2.0])]),
        }
    )

    assert arrow_table_content_hash(single_chunk) == arrow_table_content_hash(two_chunks)
