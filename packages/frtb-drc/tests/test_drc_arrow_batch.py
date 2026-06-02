from __future__ import annotations

from dataclasses import replace
from typing import cast

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import source_content_hash
from frtb_drc import (
    DrcInputError,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    input_hash_for_drc_batch,
    input_snapshot_hash,
    validate_reconciliation,
)
from frtb_drc.arrow_handoff import (
    build_drc_nonsec_batch_from_handoff,
    normalize_drc_nonsec_arrow_table,
)
from frtb_drc.batch import (
    build_drc_nonsec_batch_from_columns,
    build_drc_nonsec_batch_from_positions,
)
from frtb_drc.data_models import DrcCapitalResult, DrcPosition
from frtb_drc.demo_fixture import load_drc_nonsec_v2_fixture


def test_drc_position_batch_from_rows_matches_row_input_hash() -> None:
    fixture = load_drc_nonsec_v2_fixture()

    batch = build_drc_nonsec_batch_from_positions(fixture.positions)

    assert batch.row_count == len(fixture.positions)
    assert len(batch.input_hash) == 64
    assert input_hash_for_drc_batch(batch) == batch.input_hash
    assert batch.input_hash == build_drc_nonsec_batch_from_positions(fixture.positions).input_hash
    assert batch.input_hash != input_snapshot_hash(fixture.positions)
    assert not batch.position_ids.flags.writeable
    assert not batch.notionals.flags.writeable


def test_drc_arrow_handoff_batch_matches_nonsec_v2_row_capital() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    row_result = calculate_drc_capital(fixture.positions, context=fixture.context)
    source_hash = source_content_hash("synthetic drc nonsec source")
    handoff = normalize_drc_nonsec_arrow_table(
        _arrow_table(fixture.positions),
        source_hash=source_hash,
    )

    batch = build_drc_nonsec_batch_from_handoff(handoff)
    calculation = calculate_drc_capital_from_batch(batch, context=fixture.context)

    validate_reconciliation(calculation.result)
    assert batch.source_hash == source_hash
    assert batch.handoff_hash is not None
    assert calculation.accepted_row_dataclasses_materialized == 0
    assert calculation.result.input_positions == ()
    assert calculation.result.gross_jtds == ()
    assert calculation.result.maturity_scaled_jtds == ()
    assert calculation.result.input_hash == batch.input_hash
    assert calculation.result.profile_hash == row_result.profile_hash
    assert calculation.result.input_count == row_result.input_count
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert _net_outputs(calculation.result.net_jtds) == _net_outputs(row_result.net_jtds)
    assert _bucket_outputs(calculation.result.categories[0].bucket_results) == _bucket_outputs(
        row_result.categories[0].bucket_results
    )
    row_gross_by_id = {record.position_id: record.gross_jtd for record in row_result.gross_jtds}
    batch_gross_by_id = {
        position_id: gross
        for position_id, gross in zip(
            batch.position_ids.tolist(), calculation.gross_jtd, strict=True
        )
    }
    assert batch_gross_by_id == pytest.approx(row_gross_by_id)


def test_drc_arrow_handoff_uses_zero_copy_float64_columns_when_possible() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    handoff = normalize_drc_nonsec_arrow_table(_arrow_table(fixture.positions))

    batch = build_drc_nonsec_batch_from_handoff(handoff)

    notional_view = handoff.accepted.column("notional").chunk(0).to_numpy(zero_copy_only=True)
    maturity_view = handoff.accepted.column("maturity_years").chunk(0).to_numpy(zero_copy_only=True)
    assert np.shares_memory(batch.notionals, notional_view)
    assert np.shares_memory(batch.maturity_years, maturity_view)
    np.testing.assert_allclose(
        batch.notionals, [position.notional for position in fixture.positions]
    )


def test_drc_arrow_handoff_handles_chunked_dictionary_text_columns() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    table = pa.concat_tables(
        [
            _dictionary_encoded_text_table(_arrow_table(fixture.positions[:3])),
            _dictionary_encoded_text_table(_arrow_table(fixture.positions[3:])),
        ]
    )
    row_batch = build_drc_nonsec_batch_from_positions(fixture.positions)

    arrow_batch = build_drc_nonsec_batch_from_handoff(normalize_drc_nonsec_arrow_table(table))

    assert table.column("risk_class").num_chunks == 2
    assert pa.types.is_dictionary(table.column("risk_class").type)
    assert arrow_batch.input_hash == row_batch.input_hash
    np.testing.assert_array_equal(
        arrow_batch.position_ids,
        [position.position_id for position in fixture.positions],
    )
    np.testing.assert_array_equal(
        arrow_batch.issuer_ids,
        [position.issuer_id for position in fixture.positions],
    )
    np.testing.assert_array_equal(
        arrow_batch.seniorities,
        [
            position.seniority.value if position.seniority is not None else None
            for position in fixture.positions
        ],
    )


def test_drc_batch_lgd_lookup_is_by_seniority_and_default_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import frtb_drc.batch as batch_module

    fixture = load_drc_nonsec_v2_fixture()
    row_count = 120
    columns = _minimal_column_payload(row_count=row_count) | {
        "is_defaulted": [index % 10 == 0 for index in range(row_count)],
    }
    batch = build_drc_nonsec_batch_from_columns(**columns)
    calls: list[object] = []
    original_get_lgd_rule = batch_module.get_lgd_rule

    def counting_get_lgd_rule(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original_get_lgd_rule(*args, **kwargs)

    monkeypatch.setattr(batch_module, "get_lgd_rule", counting_get_lgd_rule)

    calculation = calculate_drc_capital_from_batch(batch, context=fixture.context)

    assert calculation.accepted_row_dataclasses_materialized == 0
    assert len(calls) == 1


def test_drc_batch_calculation_is_deterministic_for_reversed_handoff() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    table = _arrow_table(fixture.positions)
    reversed_table = table.take(pa.array(list(reversed(range(table.num_rows))), type=pa.int64()))

    first = calculate_drc_capital_from_batch(
        build_drc_nonsec_batch_from_handoff(normalize_drc_nonsec_arrow_table(table)),
        context=fixture.context,
    )
    second = calculate_drc_capital_from_batch(
        build_drc_nonsec_batch_from_handoff(normalize_drc_nonsec_arrow_table(reversed_table)),
        context=fixture.context,
    )

    assert first.result.input_hash == second.result.input_hash
    assert _net_outputs(first.result.net_jtds) == _net_outputs(second.result.net_jtds)
    assert _bucket_outputs(first.result.categories[0].bucket_results) == _bucket_outputs(
        second.result.categories[0].bucket_results
    )


def test_drc_column_batch_rejects_unsupported_risk_class_without_row_fallback() -> None:
    columns = _minimal_column_payload(row_count=1) | {"risk_classes": ["SECURITISATION_NON_CTP"]}

    with pytest.raises(DrcInputError, match="only supports non-securitisation"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_unrated_credit_quality_without_row_fallback() -> None:
    columns = _minimal_column_payload(row_count=1) | {"credit_qualities": ["UNRATED"]}

    with pytest.raises(
        DrcInputError,
        match=r"UNRATED.*not a chargeable.*US_NPR_210_B_3_II",
    ):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_high_volume_path_reports_zero_row_dataclasses() -> None:
    row_count = 1_000
    columns = _minimal_column_payload(row_count=row_count)

    batch = build_drc_nonsec_batch_from_columns(**columns)

    assert batch.row_count == row_count
    assert not any(isinstance(value, DrcPosition) for value in batch.__dict__.values())
    assert batch.input_hash


def test_drc_column_batch_copy_false_does_not_freeze_caller_numpy_arrays() -> None:
    notionals = np.array([100_000.0, 200_000.0], dtype=np.float64)
    maturity_years = np.array([1.0, 0.5], dtype=np.float64)
    columns = _minimal_column_payload(row_count=2) | {
        "notionals": notionals,
        "maturity_years": maturity_years,
    }

    batch = build_drc_nonsec_batch_from_columns(**columns, copy_arrays=False)

    assert notionals.flags.writeable
    assert maturity_years.flags.writeable
    assert not batch.notionals.flags.writeable
    assert not batch.maturity_years.flags.writeable
    assert np.shares_memory(batch.notionals, notionals)
    assert np.shares_memory(batch.maturity_years, maturity_years)


def test_drc_batch_rejects_unsupported_citation_policy_like_row_api() -> None:
    fixture = load_drc_nonsec_v2_fixture()
    batch = build_drc_nonsec_batch_from_handoff(
        normalize_drc_nonsec_arrow_table(_arrow_table(fixture.positions))
    )

    with pytest.raises(DrcInputError, match="unsupported citation_policy: lenient"):
        calculate_drc_capital_from_batch(
            batch,
            context=replace(fixture.context, citation_policy="lenient"),
        )


def test_drc_column_batch_requires_lineage() -> None:
    columns = _minimal_column_payload(row_count=1)
    columns.pop("lineage_source_systems")
    columns.pop("lineage_source_files")

    with pytest.raises(DrcInputError, match="lineage is required"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_blank_lineage_fields() -> None:
    columns = _minimal_column_payload(row_count=1) | {"lineage_source_systems": [" "]}

    with pytest.raises(DrcInputError, match=r"lineage\.source_system must be non-empty"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_column_batch_rejects_blank_citation_ids() -> None:
    columns = _minimal_column_payload(row_count=1) | {"citation_ids": [["US_NPR_210_SCOPE", " "]]}

    with pytest.raises(DrcInputError, match="citation_ids must contain non-empty citations"):
        build_drc_nonsec_batch_from_columns(**columns)


def test_drc_batch_calculation_validates_result_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import frtb_drc.batch as batch_module

    fixture = load_drc_nonsec_v2_fixture()
    batch = build_drc_nonsec_batch_from_handoff(
        normalize_drc_nonsec_arrow_table(_arrow_table(fixture.positions))
    )
    calls: list[float] = []

    def fake_validate_reconciliation(result: DrcCapitalResult) -> None:
        calls.append(result.total_drc)

    monkeypatch.setattr(batch_module, "validate_reconciliation", fake_validate_reconciliation)

    calculation = batch_module.calculate_drc_capital_from_batch(batch, context=fixture.context)

    assert calls == [calculation.result.total_drc]


def _minimal_column_payload(*, row_count: int) -> dict[str, object]:
    return {
        "position_ids": [f"p-{index:06d}" for index in range(row_count)],
        "source_row_ids": [f"row-{index:06d}" for index in range(row_count)],
        "desk_ids": ["credit-desk"] * row_count,
        "legal_entities": ["bank-na"] * row_count,
        "risk_classes": ["NON_SECURITISATION"] * row_count,
        "instrument_types": ["BOND"] * row_count,
        "default_directions": ["LONG"] * row_count,
        "issuer_ids": [f"issuer-{index % 50:03d}" for index in range(row_count)],
        "bucket_keys": ["CORPORATE"] * row_count,
        "seniorities": ["SENIOR_DEBT"] * row_count,
        "credit_qualities": ["INVESTMENT_GRADE"] * row_count,
        "notionals": [100_000.0 + index for index in range(row_count)],
        "cumulative_pnls": [0.0] * row_count,
        "maturity_years": [1.0] * row_count,
        "currencies": ["USD"] * row_count,
        "lineage_source_systems": ["unit-test"] * row_count,
        "lineage_source_files": ["synthetic-drc.csv"] * row_count,
    }


def _arrow_table(positions: tuple[DrcPosition, ...]) -> pa.Table:
    return pa.table(
        {
            "position_id": [position.position_id for position in positions],
            "source_row_id": [position.source_row_id for position in positions],
            "desk_id": [position.desk_id for position in positions],
            "legal_entity": [position.legal_entity for position in positions],
            "risk_class": [position.risk_class.value for position in positions],
            "instrument_type": [position.instrument_type.value for position in positions],
            "default_direction": [position.default_direction.value for position in positions],
            "issuer_id": [position.issuer_id for position in positions],
            "tranche_id": [position.tranche_id for position in positions],
            "index_series_id": [position.index_series_id for position in positions],
            "bucket_key": [position.bucket_key for position in positions],
            "seniority": [
                None if position.seniority is None else position.seniority.value
                for position in positions
            ],
            "credit_quality": [
                None if position.credit_quality is None else position.credit_quality.value
                for position in positions
            ],
            "notional": pa.array([position.notional for position in positions], type=pa.float64()),
            "market_value": pa.array(
                [position.market_value for position in positions], type=pa.float64()
            ),
            "cumulative_pnl": pa.array(
                [position.cumulative_pnl for position in positions], type=pa.float64()
            ),
            "maturity_years": pa.array(
                [position.maturity_years for position in positions], type=pa.float64()
            ),
            "currency": [position.currency for position in positions],
            "lgd_override": pa.array(
                [position.lgd_override for position in positions], type=pa.float64()
            ),
            "is_defaulted": [position.is_defaulted for position in positions],
            "is_gse": [position.is_gse for position in positions],
            "is_pse": [position.is_pse for position in positions],
            "is_covered_bond": [position.is_covered_bond for position in positions],
            "lineage_source_system": [
                "" if position.lineage is None else position.lineage.source_system
                for position in positions
            ],
            "lineage_source_file": [
                "" if position.lineage is None else position.lineage.source_file
                for position in positions
            ],
            "citation_ids": [",".join(position.citation_ids) for position in positions],
        }
    )


_DICTIONARY_TEXT_COLUMNS = {
    "position_id",
    "source_row_id",
    "desk_id",
    "legal_entity",
    "risk_class",
    "instrument_type",
    "default_direction",
    "issuer_id",
    "tranche_id",
    "index_series_id",
    "bucket_key",
    "seniority",
    "credit_quality",
    "currency",
    "lineage_source_system",
    "lineage_source_file",
    "citation_ids",
}


def _dictionary_encoded_text_table(table: pa.Table) -> pa.Table:
    columns = {}
    for column_name in table.column_names:
        column = table.column(column_name).combine_chunks()
        columns[column_name] = (
            column.dictionary_encode() if column_name in _DICTIONARY_TEXT_COLUMNS else column
        )
    return pa.table(columns)


def _net_outputs(records: object) -> dict[str, object]:
    return {
        record.net_jtd_id: {
            "amount": record.net_amount,
            "bucket": record.bucket_key,
            "direction": record.net_direction.value,
            "issuer": record.obligor_or_tranche_key,
            "position_ids": record.position_ids,
            "rejected_offsets": [offset.reason_code for offset in record.rejected_offsets],
        }
        for record in cast(tuple[object, ...], records)
    }


def _bucket_outputs(records: object) -> dict[str, object]:
    return {
        record.bucket_key: {
            "capital": record.capital,
            "floor_applied": record.floor_applied,
            "hbr": record.hbr.ratio,
            "weighted_long": record.weighted_long,
            "weighted_short": record.weighted_short,
        }
        for record in cast(tuple[object, ...], records)
    }
