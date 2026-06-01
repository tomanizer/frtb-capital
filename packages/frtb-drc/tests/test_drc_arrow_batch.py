from __future__ import annotations

from typing import cast

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
from frtb_drc.data_models import DrcPosition
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


def test_drc_column_batch_high_volume_path_reports_zero_row_dataclasses() -> None:
    row_count = 1_000
    columns = _minimal_column_payload(row_count=row_count)

    batch = build_drc_nonsec_batch_from_columns(**columns)

    assert batch.row_count == row_count
    assert not any(isinstance(value, DrcPosition) for value in batch.__dict__.values())
    assert batch.input_hash


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
            "notional": [position.notional for position in positions],
            "market_value": [position.market_value for position in positions],
            "cumulative_pnl": [position.cumulative_pnl for position in positions],
            "maturity_years": [position.maturity_years for position in positions],
            "currency": [position.currency for position in positions],
            "lgd_override": [position.lgd_override for position in positions],
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
